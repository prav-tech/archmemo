"""Database engine and session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Return (or create) the async SQLAlchemy engine."""
    global _engine
    if _engine is None:
        cfg = get_settings()
        # check_same_thread is only valid for SQLite; omit for PostgreSQL
        connect_args: dict = {}
        if cfg.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_async_engine(
            cfg.database_url,
            echo=cfg.debug,
            connect_args=connect_args,
        )
    return _engine


async def create_db_and_tables() -> None:
    """Create all SQLModel tables on startup (idempotent)."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    engine = get_engine()
    async_session = sessionmaker(  # type: ignore[call-overload]
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    """Session for code that runs outside a request (startup hooks, scripts)."""
    async with AsyncSession(get_engine(), expire_on_commit=False) as session:
        yield session
