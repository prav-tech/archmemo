"""
Hindsight client wrapper.

All interactions with Hindsight (retain / recall) go through this module.
Never call the Hindsight SDK directly from route handlers.

Design notes
------------
* Everything is async (`aretain` / `arecall`) so a slow retain never blocks
  the FastAPI event loop.
* Every retain carries a stable `document_id`, filterable `tags`, and string
  `metadata` containing the `decision_id`. Hindsight extracts *facts* from
  the prose, so the ID in the prose can be lost; metadata/document_id/tags
  are how each recalled fact is attributed back to a decision.
* Re-retaining the same `document_id` upserts, which makes retain idempotent
  (safe for /resync and for PATCH).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from hindsight_client import Hindsight

from app.config import get_settings
from app.memory.content import (
    decision_document_id,
    decision_metadata,
    decision_tags,
    format_decision_for_retain,
    format_outcome_for_retain,
    outcome_document_id,
    outcome_metadata,
    outcome_tags,
    parse_decision_date,
    as_utc,
)

if TYPE_CHECKING:
    from app.models.decision import Decision, Outcome

log = logging.getLogger(__name__)

_DECISION_ID_RE = re.compile(r"DEC-\d{4}-\d{3}")


@dataclass
class RecalledMemory:
    """A single fact surfaced by Hindsight recall, attributed to a decision."""

    memory_id: str
    text: str
    decision_id: str | None      # None => could not be attributed; must not be cited
    kind: str                    # "decision" | "outcome" | "unknown"
    score: float = 0.0
    tags: list[str] = field(default_factory=list)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", value.strip().lower()).strip("-")


def _attribute(result: Any) -> tuple[str | None, str]:
    """
    Work out which decision a recalled fact belongs to, and whether it came
    from the decision record or an outcome record.

    Order of trust: metadata -> document_id -> tags -> a *single unambiguous*
    ID in the text. If a fact mentions several decisions we refuse to guess.
    """
    md = getattr(result, "metadata", None) or {}
    tags = getattr(result, "tags", None) or []
    doc_id = getattr(result, "document_id", None) or ""

    decision_id = md.get("decision_id")
    if not decision_id:
        m = _DECISION_ID_RE.match(doc_id)
        decision_id = m.group(0) if m else None
    if not decision_id:
        for t in tags:
            if t.startswith("decision:"):
                decision_id = t.split(":", 1)[1]
                break
    if not decision_id:
        found = set(_DECISION_ID_RE.findall(getattr(result, "text", "") or ""))
        decision_id = next(iter(found)) if len(found) == 1 else None

    kind = md.get("kind")
    if not kind:
        if ":outcome:" in doc_id or "kind:outcome" in tags:
            kind = "outcome"
        elif "kind:decision" in tags or (doc_id and doc_id == decision_id):
            kind = "decision"
        else:
            kind = "unknown"
    return decision_id, kind


class MemoryClient:
    """Thin, typed wrapper around the Hindsight SDK (single bank)."""

    def __init__(self) -> None:
        cfg = get_settings()
        kwargs: dict[str, Any] = {"base_url": cfg.hindsight_base_url}
        if cfg.hindsight_api_key:
            kwargs["api_key"] = cfg.hindsight_api_key
        self._client = Hindsight(**kwargs)
        self._bank_id = cfg.hindsight_bank_id
        log.info("MemoryClient initialised (bank=%s, url=%s)", self._bank_id, cfg.hindsight_base_url)

    # ── retain ────────────────────────────────────────────────────────────

    async def retain_decision(self, decision: "Decision") -> None:
        """Retain (upsert) a decision. Raises on failure; callers decide how to surface it."""
        log.info("retain decision %s", decision.decision_id)
        await self._client.aretain(
            bank_id=self._bank_id,
            content=format_decision_for_retain(decision),
            context=f"Architecture decision record {decision.decision_id}",
            document_id=decision_document_id(decision.decision_id),
            timestamp=parse_decision_date(decision.date),
            metadata=decision_metadata(decision),
            tags=decision_tags(decision),
        )

    async def retain_outcome(self, decision: "Decision", outcome: "Outcome") -> None:
        """Retain (upsert) a measured outcome for a decision."""
        log.info("retain outcome %s for decision %s", outcome.id, decision.decision_id)
        await self._client.aretain(
            bank_id=self._bank_id,
            content=format_outcome_for_retain(decision, outcome),
            context=f"Measured outcome of architecture decision {decision.decision_id}",
            document_id=outcome_document_id(decision.decision_id, outcome.id),
            timestamp=as_utc(outcome.recorded_at),
            metadata=outcome_metadata(decision, outcome),
            tags=outcome_tags(decision, outcome),
        )

    # ── recall ────────────────────────────────────────────────────────────

    async def recall_for_briefing(
        self,
        query: str,
        top_k: int | None = None,
        domain: str | None = None,
        services: list[str] | None = None,
    ) -> list[RecalledMemory]:
        """
        Semantic recall for a proposal, with optional metadata (tag) filters.

        `domain` / `services` narrow recall to memories tagged with any of
        them (`any_strict`: untagged memories are excluded when filtering).
        Returns memories in Hindsight's relevance order, capped at top_k.
        """
        cfg = get_settings()
        k = top_k or cfg.recall_top_k
        query = query[: cfg.recall_query_max_chars]

        tags: list[str] = []
        if domain:
            tags.append(f"domain:{_slug(domain)}")
        tags += [f"service:{_slug(s)}" for s in services or []]

        log.info("recall (bank=%s, k=%d, filters=%s)", self._bank_id, k, tags or None)
        kwargs: dict[str, Any] = {"bank_id": self._bank_id, "query": query}
        if tags:
            kwargs["tags"] = tags
            kwargs["tags_match"] = "any_strict"
        result = await self._client.arecall(**kwargs)

        memories: list[RecalledMemory] = []
        for r in result.results[:k]:
            decision_id, kind = _attribute(r)
            scores = getattr(r, "scores", None)
            memories.append(
                RecalledMemory(
                    memory_id=r.id,
                    text=r.text,
                    decision_id=decision_id,
                    kind=kind,
                    score=float(getattr(scores, "final", 0.0) or 0.0),
                    tags=list(getattr(r, "tags", None) or []),
                )
            )
        log.info("recall returned %d memories", len(memories))
        return memories


# ── Module-level singleton ─────────────────────────────────────────────────
_memory_client: MemoryClient | None = None


def get_memory_client() -> MemoryClient:
    """Return the module-level MemoryClient singleton (lazily created)."""
    global _memory_client
    if _memory_client is None:
        _memory_client = MemoryClient()
    return _memory_client
