"""
Decision CRUD routes.

POST   /api/decisions            – create a new ADR (retain to Hindsight)
GET    /api/decisions            – list all decisions (filter: domain, status, tag)
GET    /api/decisions/{id}       – get decision detail with outcome count
PATCH  /api/decisions/{id}       – update decision metadata (re-retains to Hindsight)
POST   /api/decisions/{id}/resync – re-retain decision + outcomes (repair after Hindsight outage)
GET    /api/decisions/{id}/export – export the ADR and its outcomes as Markdown
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.export import render_decision_markdown
from app.memory.client import get_memory_client
from app.models.decision import Decision, Outcome

log = logging.getLogger(__name__)
router = APIRouter()

# Valid status values – enforced at the API layer
VALID_STATUSES = {"active", "superseded", "deprecated"}


# ── Request / Response schemas ────────────────────────────────────────────


class DecisionCreate(BaseModel):
    """Payload for creating a new architecture decision."""

    title: str = Field(..., min_length=5, max_length=200)
    date: str = Field(..., description="ISO-8601 date, e.g. 2024-03-15")
    authors: str = Field(..., min_length=2)
    domain: str = Field(..., min_length=2)
    services: list[str] = Field(default_factory=list)
    context: str = Field(..., min_length=20)
    forces: str | None = None
    options: list[str] = Field(default_factory=list)
    chosen_option: str = Field(..., min_length=2)
    rationale: str = Field(..., min_length=20)
    expected_outcomes: str | None = None
    tags: list[str] = Field(default_factory=list)
    related_decisions: list[str] = Field(default_factory=list)
    status: str = Field(default="active")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        return v

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError("date must be ISO-8601 format, e.g. 2024-03-15")
        return v


class DecisionUpdate(BaseModel):
    """Partial update payload – all fields optional."""

    title: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    related_decisions: list[str] | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}")
        return v


class DecisionOut(BaseModel):
    """Flat response shape for a Decision."""

    decision_id: str
    title: str
    date: str
    authors: str
    domain: str
    services: list[str]
    status: str
    context: str
    forces: str | None
    options: list[str]
    chosen_option: str
    rationale: str
    expected_outcomes: str | None
    tags: list[str]
    related_decisions: list[str]
    created_at: datetime
    updated_at: datetime
    outcome_count: int = 0
    memory_synced: bool = False

    model_config = {"from_attributes": True}


# ── Helpers ───────────────────────────────────────────────────────────────


async def _next_decision_id(session: AsyncSession) -> str:
    """Generate the next sequential DEC-YYYY-NNN id.

    Scans existing IDs for the current year and increments the highest
    sequence number. Purely sequential; not distributed-safe (fine for MVP).
    """
    year = datetime.now(timezone.utc).year
    prefix = f"DEC-{year}-"
    result = await session.exec(
        select(Decision.decision_id)
        .where(Decision.decision_id.like(f"{prefix}%"))  # type: ignore[attr-defined]
        .order_by(Decision.decision_id.desc())  # type: ignore[attr-defined]
        .limit(1)
    )
    last = result.first()
    if last:
        num = int(last.split("-")[-1]) + 1
    else:
        num = 1
    return f"{prefix}{num:03d}"


async def _decision_or_404(decision_id: str, session: AsyncSession) -> Decision:
    """Fetch a decision by ID or raise a 404 HTTPException."""
    dec = await session.get(Decision, decision_id)
    if not dec:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id!r} not found")
    return dec


async def _count_outcomes(decision_id: str, session: AsyncSession) -> int:
    """Return the number of outcomes attached to a decision."""
    result = await session.exec(
        select(func.count()).where(Outcome.decision_id == decision_id)  # type: ignore[arg-type]
    )
    return result.first() or 0


async def _build_outcome_count_map(
    decision_ids: list[str],
    session: AsyncSession,
) -> dict[str, int]:
    """
    Fetch outcome counts for a list of decision IDs in a single query.

    This avoids the N+1 query problem when listing many decisions.
    Returns a dict mapping decision_id → outcome count.
    """
    if not decision_ids:
        return {}
    result = await session.exec(
        select(Outcome.decision_id, func.count().label("cnt"))  # type: ignore[arg-type]
        .where(Outcome.decision_id.in_(decision_ids))  # type: ignore[attr-defined]
        .group_by(Outcome.decision_id)
    )
    return {row[0]: row[1] for row in result.all()}


async def _retain_decision_or_503(dec: Decision, session: AsyncSession) -> None:
    """
    Retain a decision to Hindsight and record the result in SQL.

    Retain is an upsert keyed on decision_id, so calling this again is safe.
    On failure the SQL row is kept (memory_synced=False) and we return 503
    with the repair endpoint, instead of pretending the memory was stored.
    """
    try:
        await get_memory_client().retain_decision(dec)
    except Exception as exc:
        log.exception("Hindsight retain failed for %s; SQL record kept", dec.decision_id)
        dec.memory_synced = False
        session.add(dec)
        await session.commit()
        raise HTTPException(
            status_code=503,
            detail=(
                f"Decision {dec.decision_id} was saved but could not be retained to "
                f"Hindsight ({exc}). Once Hindsight is reachable, call "
                f"POST /api/decisions/{dec.decision_id}/resync."
            ),
        ) from exc
    dec.memory_synced = True
    session.add(dec)
    await session.commit()
    await session.refresh(dec)


# ── Routes ────────────────────────────────────────────────────────────────


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DecisionOut)
async def create_decision(
    payload: DecisionCreate,
    session: AsyncSession = Depends(get_session),
) -> DecisionOut:
    """
    Create a new Architecture Decision Record.

    Persists a lightweight pointer to SQL and retains rich natural-language
    content to Hindsight. The Hindsight retain call happens after the SQL
    commit succeeds, so the SQL record is always the source of truth.
    If Hindsight is unavailable the endpoint will return a 503 rather than
    silently succeeding with an incomplete memory store.
    """
    decision_id = await _next_decision_id(session)

    dec = Decision(
        decision_id=decision_id,
        **payload.model_dump(),
    )
    session.add(dec)
    await session.commit()
    await session.refresh(dec)

    # Retain to Hindsight – always after SQL commit
    await _retain_decision_or_503(dec, session)

    log.info("Created decision %s and retained to Hindsight", decision_id)
    return DecisionOut(**dec.model_dump(), outcome_count=0)


@router.get("", response_model=list[DecisionOut])
async def list_decisions(
    domain: str | None = Query(default=None, description="Filter by domain"),
    status: str | None = Query(default=None, description="Filter by status"),
    tag: str | None = Query(default=None, description="Filter by tag"),
    session: AsyncSession = Depends(get_session),
) -> list[DecisionOut]:
    """
    List all decisions with optional filters.

    Outcome counts are fetched in a single batch query (no N+1).
    """
    stmt = select(Decision).order_by(Decision.date.desc())  # type: ignore[attr-defined]
    if domain:
        stmt = stmt.where(Decision.domain == domain)  # type: ignore[arg-type]
    if status:
        stmt = stmt.where(Decision.status == status)  # type: ignore[arg-type]

    result = await session.exec(stmt)
    decisions = list(result.all())

    # Tag filter applied in-memory (SQLite JSON path queries are limited)
    if tag:
        decisions = [d for d in decisions if tag in (d.tags or [])]

    # Single batch query for all outcome counts
    count_map = await _build_outcome_count_map(
        [d.decision_id for d in decisions], session
    )

    return [
        DecisionOut(**dec.model_dump(), outcome_count=count_map.get(dec.decision_id, 0))
        for dec in decisions
    ]


@router.get("/{decision_id}", response_model=DecisionOut)
async def get_decision(
    decision_id: str,
    session: AsyncSession = Depends(get_session),
) -> DecisionOut:
    """Get a single decision with its outcome count."""
    dec = await _decision_or_404(decision_id, session)
    count = await _count_outcomes(decision_id, session)
    return DecisionOut(**dec.model_dump(), outcome_count=count)


@router.patch("/{decision_id}", response_model=DecisionOut)
async def update_decision(
    decision_id: str,
    payload: DecisionUpdate,
    session: AsyncSession = Depends(get_session),
) -> DecisionOut:
    """
    Partially update a decision's mutable metadata fields.

    Only `title`, `status`, `tags`, and `related_decisions` are patchable.
    The full ADR content (context, rationale, etc.) is immutable; create a
    new decision to supersede it.
    """
    dec = await _decision_or_404(decision_id, session)
    update_data = payload.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    for k, v in update_data.items():
        setattr(dec, k, v)
    dec.updated_at = datetime.now(timezone.utc)
    session.add(dec)
    await session.commit()
    await session.refresh(dec)

    # Status/tags/title feed Hindsight tags and prose; re-retain (upsert) so
    # memory never disagrees with SQL (e.g. a decision marked superseded).
    await _retain_decision_or_503(dec, session)

    count = await _count_outcomes(decision_id, session)
    return DecisionOut(**dec.model_dump(), outcome_count=count)


@router.post("/{decision_id}/resync", response_model=dict)
async def resync_decision(
    decision_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Re-retain a decision and all its outcomes to Hindsight.

    Idempotent (document_id upsert). Use after a Hindsight outage left
    records with memory_synced=false.
    """
    dec = await _decision_or_404(decision_id, session)
    await _retain_decision_or_503(dec, session)

    result = await session.exec(select(Outcome).where(Outcome.decision_id == decision_id))
    synced = 0
    for outcome in result.all():
        try:
            await get_memory_client().retain_outcome(dec, outcome)
        except Exception as exc:
            log.exception("resync: outcome %s retain failed", outcome.id)
            outcome.memory_synced = False
            session.add(outcome)
            await session.commit()
            raise HTTPException(
                status_code=503, detail=f"Outcome {outcome.id} could not be retained: {exc}"
            ) from exc
        outcome.memory_synced = True
        session.add(outcome)
        synced += 1
    await session.commit()
    return {"decision_id": decision_id, "decision_synced": True, "outcomes_synced": synced}


@router.get("/{decision_id}/export", response_model=dict)
async def export_decision_markdown(
    decision_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Export a decision, with every recorded outcome, as one Markdown document."""
    dec = await _decision_or_404(decision_id, session)
    result = await session.exec(
        select(Outcome).where(Outcome.decision_id == decision_id).order_by(Outcome.recorded_at)  # type: ignore[arg-type]
    )
    md = render_decision_markdown(
        dec, list(result.all()), generated_on=datetime.now(timezone.utc).date()
    )
    return {"decision_id": decision_id, "markdown": md}
