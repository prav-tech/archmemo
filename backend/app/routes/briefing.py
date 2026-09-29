"""
Briefing route – the core value proposition of ArchMemory.

POST /api/briefing

Accepts a new RFC/proposal, recalls relevant past decisions + outcomes from
Hindsight, and returns a briefing grounded in that recalled history.

Grounding guarantees (enforced in code, not just in the prompt):
1. No recalled memory  -> the LLM is NOT called; a fixed "no memory" briefing is returned.
2. Every recalled fact is labelled with its decision ID; the LLM may only cite those.
3. After generation, every cited ID is checked against the recalled set.
   Unverified IDs are flagged in the text, reported, and audited.
4. The audit log records what was actually recalled, what was cited, and what was rejected.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.deps import CurrentUser, require_user
from app.db import get_session
from app.llm import complete_chat
from app.memory.client import RecalledMemory, get_memory_client
from app.models.decision import BriefingAudit, Decision, Outcome
from app.prompts import BRIEFING_SYSTEM_PROMPT, NO_MEMORY_BRIEFING

log = logging.getLogger(__name__)
router = APIRouter()

_ID_RE = re.compile(r"DEC-\d{4}-\d{3}")


# ── Schemas ───────────────────────────────────────────────────────────────


class BriefingRequest(BaseModel):
    proposal: str = Field(..., min_length=50, description="Full RFC or proposal text")
    top_k: int | None = Field(default=None, ge=1, le=40, description="Override recall size")
    domain: str | None = Field(default=None, description="Optional recall filter, e.g. 'data'")
    services: list[str] | None = Field(default=None, description="Optional recall filter")
    requested_by: str | None = None


class CitedDecision(BaseModel):
    decision_id: str
    title: str | None = None
    relevance_excerpt: str
    verified: bool = True  # False => the LLM cited an ID that was not in the recalled memory


class RecalledDecision(BaseModel):
    """What the agent actually had to work with for one decision."""

    decision_id: str
    title: str | None
    has_outcome_memory: bool   # an outcome fact was recalled and shown to the LLM
    outcomes_on_record: int    # outcomes stored in SQL (may exceed what was recalled)


class BriefingResponse(BaseModel):
    briefing: str
    cited_decisions: list[CitedDecision]
    unverified_citations: list[str]
    recalled_decisions: list[RecalledDecision]
    recalled_memory_count: int
    model_used: str
    latency_ms: int
    audit_id: int | None = None


# ── Helpers ───────────────────────────────────────────────────────────────


async def _registry_lookup(
    decision_ids: list[str], session: AsyncSession
) -> tuple[dict[str, Decision], dict[str, int]]:
    """Titles/dates/status and outcome counts from SQL for the recalled decisions."""
    if not decision_ids:
        return {}, {}
    dec_rows = await session.exec(
        select(Decision).where(Decision.decision_id.in_(decision_ids))  # type: ignore[attr-defined]
    )
    decisions = {d.decision_id: d for d in dec_rows.all()}
    cnt_rows = await session.exec(
        select(Outcome.decision_id, func.count())  # type: ignore[arg-type]
        .where(Outcome.decision_id.in_(decision_ids))  # type: ignore[attr-defined]
        .group_by(Outcome.decision_id)
    )
    return decisions, {row[0]: row[1] for row in cnt_rows.all()}


def _group_by_decision(memories: list[RecalledMemory]) -> tuple[dict[str, list[RecalledMemory]], list[RecalledMemory]]:
    """Group memories by decision ID (first-seen order = relevance order)."""
    grouped: dict[str, list[RecalledMemory]] = {}
    unattributed: list[RecalledMemory] = []
    for m in memories:
        if m.decision_id:
            grouped.setdefault(m.decision_id, []).append(m)
        else:
            unattributed.append(m)
    return grouped, unattributed


def _build_user_prompt(
    proposal: str,
    grouped: dict[str, list[RecalledMemory]],
    unattributed: list[RecalledMemory],
    registry: dict[str, Decision],
    outcome_counts: dict[str, int],
) -> str:
    """Inject recalled facts, each under an ID header the model is allowed to cite."""
    blocks: list[str] = []
    for dec_id, mems in grouped.items():
        dec = registry.get(dec_id)
        title = dec.title if dec else "(title unavailable)"
        meta = f"decided {dec.date}, status: {dec.status}" if dec else "not in registry"
        n_out = outcome_counts.get(dec_id, 0)
        if n_out == 0:
            outcome_note = "no outcome recorded"
        else:
            outcome_note = f"{n_out} outcome(s) on record"
        lines = [f"### {dec_id} | {title} | {meta} | {outcome_note}"]
        lines += [f"[{m.kind.upper()}] {m.text}" for m in mems]
        blocks.append("\n".join(lines))

    if unattributed:
        blocks.append(
            "### UNATTRIBUTED (no decision ID – do not cite)\n"
            + "\n".join(f"- {m.text}" for m in unattributed)
        )

    evidence = "\n\n".join(blocks)
    return f"""EVIDENCE (recalled from institutional memory)
================================================
{evidence}
================================================
END OF EVIDENCE

NEW PROPOSAL TO REVIEW
================================================
{proposal}
================================================
END OF PROPOSAL

Produce the briefing in the required structure. Cite only IDs that appear in an evidence header above."""


def _excerpt_for(decision_id: str, text: str) -> str:
    """Best short explanation of why a decision was cited (prefers 'Why this matters')."""
    section = re.search(
        rf"###[^\n]*{re.escape(decision_id)}[^\n]*\n(.*?)(?=\n##|\Z)", text, re.DOTALL
    )
    if section:
        why = re.search(r"\*\*Why this matters[^*]*\*\*\s*(.+)", section.group(1))
        if why:
            return why.group(1).strip()[:250]
    for line in text.splitlines():
        if decision_id in line and not line.lstrip().startswith("#"):
            return re.sub(r"^[\s>*\-•]+", "", line).strip()[:250]
    return f"Referenced in briefing as {decision_id}"


def _verify_citations(
    briefing_text: str,
    recalled_ids: set[str],
) -> tuple[str, list[str], list[str]]:
    """
    Split cited IDs into verified (present in recall) and unverified.

    Unverified IDs are annotated in the briefing text so a reader can never
    mistake a fabricated citation for real evidence.
    """
    cited = list(dict.fromkeys(_ID_RE.findall(briefing_text)))
    verified = [c for c in cited if c in recalled_ids]
    unverified = [c for c in cited if c not in recalled_ids]
    if unverified:
        bad = set(unverified)
        briefing_text = _ID_RE.sub(
            lambda m: f"{m.group(0)} ⚠ UNVERIFIED – not in recalled memory"
            if m.group(0) in bad
            else m.group(0),
            briefing_text,
        )
    return briefing_text, verified, unverified


# ── Route ─────────────────────────────────────────────────────────────────


@router.post("/briefing", response_model=BriefingResponse)
async def generate_briefing(
    payload: BriefingRequest,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_user),
) -> BriefingResponse:
    """Generate a grounded architectural briefing for a new proposal."""
    if not payload.proposal.strip():
        raise HTTPException(status_code=400, detail="Proposal text is required")

    start = time.monotonic()

    # ── 1. Recall from Hindsight ──────────────────────────────────────────
    try:
        memories = await get_memory_client().recall_for_briefing(
            query=payload.proposal,
            top_k=payload.top_k,
            domain=payload.domain,
            services=payload.services,
        )
    except Exception as exc:
        log.exception("Hindsight recall failed")
        raise HTTPException(
            status_code=503, detail=f"Memory recall failed: {exc}. Is Hindsight running?"
        ) from exc

    grouped, unattributed = _group_by_decision(memories)
    if unattributed:
        log.warning("%d recalled memories had no decision ID", len(unattributed))
    recalled_ids = set(grouped)
    registry, outcome_counts = await _registry_lookup(list(grouped), session)

    # ── 2/3. Generate (or refuse to) ──────────────────────────────────────
    if not grouped:
        # Nothing citable was recalled. Calling the LLM here would only invite
        # it to answer from parametric knowledge, which is the one thing this
        # product must not do.
        log.warning("No citable memory recalled – returning fixed no-memory briefing")
        briefing_text, model_used = NO_MEMORY_BRIEFING, "none (no memory recalled)"
    else:
        user_prompt = _build_user_prompt(
            payload.proposal, grouped, unattributed, registry, outcome_counts
        )
        try:
            briefing_text, model_used = await complete_chat(BRIEFING_SYSTEM_PROMPT, user_prompt)
        except Exception as exc:
            log.exception("LLM call failed")
            raise HTTPException(status_code=503, detail=f"LLM request failed: {exc}") from exc
        if not briefing_text:
            raise HTTPException(status_code=502, detail="LLM returned an empty briefing")

    # ── 4. Verify citations against what was actually recalled ────────────
    briefing_text, verified_ids, unverified_ids = _verify_citations(briefing_text, recalled_ids)
    if unverified_ids:
        log.warning("LLM cited IDs not present in recall: %s", unverified_ids)

    cited = [
        CitedDecision(
            decision_id=i,
            title=registry[i].title if i in registry else None,
            relevance_excerpt=_excerpt_for(i, briefing_text),
            verified=True,
        )
        for i in verified_ids
    ] + [
        CitedDecision(
            decision_id=i, title=None, relevance_excerpt="Cited by the model but not present in recalled memory.",
            verified=False,
        )
        for i in unverified_ids
    ]

    recalled_decisions = [
        RecalledDecision(
            decision_id=dec_id,
            title=registry[dec_id].title if dec_id in registry else None,
            has_outcome_memory=any(m.kind == "outcome" for m in mems),
            outcomes_on_record=outcome_counts.get(dec_id, 0),
        )
        for dec_id, mems in grouped.items()
    ]

    latency_ms = int((time.monotonic() - start) * 1000)

    # ── 5. Audit: what was recalled, cited, and rejected ──────────────────
    audit = BriefingAudit(
        proposal_excerpt=payload.proposal[:500],
        recalled_decision_ids=list(grouped),
        recalled_memory_count=len(memories),
        recalled_memories=[
            {
                "memory_id": m.memory_id,
                "decision_id": m.decision_id,
                "kind": m.kind,
                "score": round(m.score, 4),
                "text": m.text[:600],
            }
            for m in memories
        ],
        cited_decision_ids=verified_ids,
        unverified_citation_ids=unverified_ids,
        filters={"domain": payload.domain, "services": payload.services}
        if (payload.domain or payload.services)
        else None,
        briefing_text=briefing_text,
        model_used=model_used,
        requested_at=datetime.now(timezone.utc),
        # The audit log must record who actually asked, so a signed-in user's
        # identity wins over anything the client put in the payload.
        requested_by=payload.requested_by if user.anonymous else user.username,
        latency_ms=latency_ms,
    )
    session.add(audit)
    await session.commit()
    await session.refresh(audit)

    log.info(
        "Briefing: %d memories / %d decisions recalled, %d cited, %d unverified, %dms",
        len(memories), len(grouped), len(verified_ids), len(unverified_ids), latency_ms,
    )

    return BriefingResponse(
        briefing=briefing_text,
        cited_decisions=cited,
        unverified_citations=unverified_ids,
        recalled_decisions=recalled_decisions,
        recalled_memory_count=len(memories),
        model_used=model_used,
        latency_ms=latency_ms,
        audit_id=audit.id,
    )
