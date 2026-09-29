"""
Outcome routes.

POST  /api/decisions/{id}/outcomes   – attach an outcome to a decision
GET   /api/decisions/{id}/outcomes   – list outcomes for a decision
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.deps import CurrentUser, require_user
from app.db import get_session
from app.memory.client import get_memory_client
from app.models.decision import Decision, Outcome

log = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────


class OutcomeCreate(BaseModel):
    """Payload for recording an outcome against an existing decision."""

    actual_results: str = Field(..., min_length=20)
    regret_score: int = Field(..., ge=1, le=5)
    lessons: str = Field(..., min_length=10)
    would_repeat: bool
    metrics: dict[str, Any] | None = None
    incidents: str | None = None
    recorded_by: str | None = None


class OutcomeOut(BaseModel):
    """Response shape for an Outcome."""

    id: int
    decision_id: str
    actual_results: str
    regret_score: int
    lessons: str
    would_repeat: bool
    metrics: dict[str, Any] | None
    incidents: str | None
    recorded_at: datetime
    recorded_by: str | None
    memory_synced: bool = False

    model_config = {"from_attributes": True}


# ── Routes ────────────────────────────────────────────────────────────────


@router.post(
    "/{decision_id}/outcomes",
    status_code=status.HTTP_201_CREATED,
    response_model=OutcomeOut,
)
async def attach_outcome(
    decision_id: str,
    payload: OutcomeCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_user),
) -> OutcomeOut:
    """
    Record an outcome for an existing decision.

    This is the key learning loop: once an outcome is attached,
    future recall will surface both the decision AND its real measured
    results, making briefings progressively more grounded.
    """
    dec = await session.get(Decision, decision_id)
    if not dec:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id!r} not found")

    data = payload.model_dump()
    # Attribute the outcome to the signed-in user unless the form named a team.
    if not data.get("recorded_by") and not user.anonymous:
        data["recorded_by"] = user.username
    outcome = Outcome(decision_id=decision_id, **data)
    session.add(outcome)
    await session.commit()
    await session.refresh(outcome)

    # Retain outcome to Hindsight (upsert keyed on decision_id + outcome id).
    # The SQL row is kept on failure and can be repaired via /resync.
    try:
        await get_memory_client().retain_outcome(dec, outcome)
    except Exception as exc:
        log.exception("Hindsight retain failed for outcome %s on %s", outcome.id, decision_id)
        raise HTTPException(
            status_code=503,
            detail=(
                f"Outcome saved (id={outcome.id}) but could not be retained to Hindsight "
                f"({exc}). Once Hindsight is reachable, call "
                f"POST /api/decisions/{decision_id}/resync."
            ),
        ) from exc
    outcome.memory_synced = True
    session.add(outcome)
    await session.commit()
    await session.refresh(outcome)

    log.info(
        "Outcome recorded for %s (regret=%d, repeat=%s)",
        decision_id,
        payload.regret_score,
        payload.would_repeat,
    )
    return OutcomeOut(**outcome.model_dump())


@router.get("/{decision_id}/outcomes", response_model=list[OutcomeOut])
async def list_outcomes(
    decision_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[OutcomeOut]:
    """List all outcomes recorded for a decision."""
    dec = await session.get(Decision, decision_id)
    if not dec:
        raise HTTPException(status_code=404, detail=f"Decision {decision_id!r} not found")

    result = await session.exec(
        select(Outcome).where(Outcome.decision_id == decision_id).order_by(Outcome.recorded_at)
    )
    outcomes = result.all()
    return [OutcomeOut(**o.model_dump()) for o in outcomes]
