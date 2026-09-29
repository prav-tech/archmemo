"""
Audit log routes.

GET  /api/audit          – list recent briefing audit entries
GET  /api/audit/{id}     – get a single audit entry
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.models.decision import BriefingAudit

router = APIRouter()


class AuditOut(BaseModel):
    id: int
    proposal_excerpt: str
    recalled_decision_ids: list[str]
    recalled_memory_count: int
    recalled_memories: list[dict]
    cited_decision_ids: list[str]
    unverified_citation_ids: list[str]
    filters: dict | None
    briefing_text: str
    model_used: str
    requested_at: datetime
    requested_by: str | None
    latency_ms: int | None

    model_config = {"from_attributes": True}


@router.get("/audit", response_model=list[AuditOut])
async def list_audits(
    session: AsyncSession = Depends(get_session),
) -> list[AuditOut]:
    """List the 50 most recent briefing audit entries."""
    result = await session.exec(
        select(BriefingAudit).order_by(BriefingAudit.requested_at.desc()).limit(50)  # type: ignore[attr-defined]
    )
    return [AuditOut(**a.model_dump()) for a in result.all()]


@router.get("/audit/{audit_id}", response_model=AuditOut)
async def get_audit(
    audit_id: int,
    session: AsyncSession = Depends(get_session),
) -> AuditOut:
    """Get a single briefing audit entry."""
    entry = await session.get(BriefingAudit, audit_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Audit entry {audit_id} not found")
    return AuditOut(**entry.model_dump())
