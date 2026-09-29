"""
Application user (login account).

Kept in its own module so scripts that only need decisions/outcomes (e.g. the
seed script) do not register, create, or drop the users table.

Like decision.py, this avoids `from __future__ import annotations` so SQLModel
can resolve field types at runtime.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    # Stored lower-case; lookups normalise the same way (see auth.service).
    username: str = Field(index=True, unique=True)
    password_hash: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
