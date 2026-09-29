"""
SQLModel database models for Decision, Outcome, and BriefingAudit.

These are lightweight pointer records. The authoritative rich content
lives in Hindsight; SQL is only used for listing, filtering, and
foreign-key relationships.

NOTE: We avoid `from __future__ import annotations` here because SQLModel
Relationship() type resolution depends on runtime annotation evaluation.
Use `Optional` and explicit `List` instead of the PEP 604/585 shorthands
to stay compatible with SQLAlchemy 2.x mapper initialization.
"""

from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, Relationship, SQLModel


# ── Decision ──────────────────────────────────────────────────────────────


class Decision(SQLModel, table=True):
    """Pointer record for an Architecture Decision Record."""

    __tablename__ = "decisions"

    # Primary key is the human-readable ID, e.g. DEC-2024-001
    decision_id: str = Field(primary_key=True)

    title: str
    date: str                               # ISO-8601 date string, e.g. 2024-03-15
    authors: str                            # comma-separated or free text
    domain: str                             # e.g. data, platform, security
    services: List[str] = Field(default=[], sa_column=Column(JSON))
    status: str = Field(default="active")   # active | superseded | deprecated

    # Rich structured fields (stored here for export / display)
    context: str
    forces: Optional[str] = None
    options: List[str] = Field(default=[], sa_column=Column(JSON))
    chosen_option: str
    rationale: str
    expected_outcomes: Optional[str] = None
    tags: List[str] = Field(default=[], sa_column=Column(JSON))
    related_decisions: List[str] = Field(default=[], sa_column=Column(JSON))

    # False until the decision has been successfully retained in Hindsight.
    # Lets us find and repair records if Hindsight was down (see /resync).
    memory_synced: bool = Field(default=False)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationship – use Optional[List[...]] to satisfy SQLAlchemy 2.x mapper
    outcomes: List["Outcome"] = Relationship(back_populates="decision")


# ── Outcome ───────────────────────────────────────────────────────────────


class Outcome(SQLModel, table=True):
    """Pointer record for an Outcome attached to a Decision."""

    __tablename__ = "outcomes"

    id: Optional[int] = Field(default=None, primary_key=True)
    decision_id: str = Field(foreign_key="decisions.decision_id", index=True)

    metrics: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    incidents: Optional[str] = None
    actual_results: str
    regret_score: int = Field(ge=1, le=5)   # 1 = no regret, 5 = strong regret
    lessons: str
    would_repeat: bool
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    recorded_by: Optional[str] = None
    memory_synced: bool = Field(default=False)

    # Relationship back to decision
    decision: Optional[Decision] = Relationship(back_populates="outcomes")


# ── Audit Log ─────────────────────────────────────────────────────────────


class BriefingAudit(SQLModel, table=True):
    """
    Audit log entry for every briefing request.

    Records which proposal was analysed, which memories were recalled,
    and the full generated briefing text. Allows engineers to review
    the agent's behaviour and verify citations.
    """

    __tablename__ = "briefing_audits"

    id: Optional[int] = Field(default=None, primary_key=True)
    proposal_excerpt: str           # First 500 chars of the proposal
    # Decision IDs Hindsight actually returned (the LLM's only allowed evidence)
    recalled_decision_ids: List[str] = Field(default=[], sa_column=Column(JSON))
    recalled_memory_count: int = Field(default=0)
    # Per-memory trail: [{memory_id, decision_id, kind, score, text}]
    recalled_memories: List[dict] = Field(default=[], sa_column=Column(JSON))
    # IDs the LLM cited that were present in recall (verified) vs. not (rejected)
    cited_decision_ids: List[str] = Field(default=[], sa_column=Column(JSON))
    unverified_citation_ids: List[str] = Field(default=[], sa_column=Column(JSON))
    filters: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    briefing_text: str
    model_used: str
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    requested_by: Optional[str] = None      # username if auth enabled
    latency_ms: Optional[int] = None        # end-to-end latency in milliseconds
