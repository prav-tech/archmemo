"""
Missing outcomes view.

GET  /api/decisions/missing-outcomes

Returns decisions that have no outcomes recorded yet, sorted by age.
Useful for nudging teams to close the learning loop.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.models.decision import Decision, Outcome

router = APIRouter()


class MissingOutcomeItem(BaseModel):
    decision_id: str
    title: str
    date: str
    domain: str
    authors: str
    days_without_outcome: int

    model_config = {"from_attributes": True}


@router.get("/decisions/missing-outcomes", response_model=list[MissingOutcomeItem])
async def list_missing_outcomes(
    session: AsyncSession = Depends(get_session),
) -> list[MissingOutcomeItem]:
    """Return active decisions with no recorded outcomes."""
    # Subquery: all decision_ids that have at least one outcome
    subq = select(Outcome.decision_id).distinct()
    result_with = await session.exec(subq)
    ids_with_outcomes = set(result_with.all())

    # All active decisions
    result_all = await session.exec(
        select(Decision).where(Decision.status == "active").order_by(Decision.date)  # type: ignore[arg-type]
    )
    all_active = result_all.all()

    today = datetime.now(timezone.utc).date()
    missing = []
    for dec in all_active:
        if dec.decision_id not in ids_with_outcomes:
            try:
                dec_date = datetime.fromisoformat(dec.date).date()
            except ValueError:
                dec_date = today
            days = max((today - dec_date).days, 0)  # a future-dated decision is age 0
            missing.append(
                MissingOutcomeItem(
                    decision_id=dec.decision_id,
                    title=dec.title,
                    date=dec.date,
                    domain=dec.domain,
                    authors=dec.authors,
                    days_without_outcome=days,
                )
            )

    return sorted(missing, key=lambda x: x.days_without_outcome, reverse=True)
