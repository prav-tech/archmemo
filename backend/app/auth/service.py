"""User persistence and first-run bootstrap."""

from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.security import hash_password, validate_new_password
from app.config import get_settings
from app.db import session_scope
from app.models.user import User

log = logging.getLogger(__name__)


def normalize_username(username: str) -> str:
    return username.strip().lower()


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.exec(
        select(User).where(User.username == normalize_username(username))  # type: ignore[arg-type]
    )
    return result.first()



async def create_user(session: AsyncSession, username: str, password: str) -> User:
    """Create an account. Raises ValueError for a bad username/password or a duplicate."""
    name = normalize_username(username)
    if not (1 <= len(name) <= 64):
        raise ValueError("Username must be 1-64 characters.")
    problem = validate_new_password(password)
    if problem:
        raise ValueError(problem)
    if await get_user_by_username(session, name):
        raise ValueError(f"User {name!r} already exists.")
    user = User(username=name, password_hash=hash_password(password))
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:  # lost a race with another process
        await session.rollback()
        raise ValueError(f"User {name!r} already exists.") from exc
    await session.refresh(user)
    return user


async def set_password(session: AsyncSession, username: str, password: str) -> User:
    """Change an existing account's password. Raises ValueError if it does not exist."""
    problem = validate_new_password(password)
    if problem:
        raise ValueError(problem)
    user = await get_user_by_username(session, username)
    if not user:
        raise ValueError(f"User {normalize_username(username)!r} does not exist.")
    user.password_hash = hash_password(password)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def ensure_bootstrap_admin() -> None:
    """
    First-run convenience: create the ADMIN_* account when there are no users.

    Only acts on an empty users table, so editing ADMIN_PASSWORD later never
    silently resets a password, and a deleted admin is not resurrected.
    """
    cfg = get_settings()
    if not cfg.auth_enabled:
        return
    async with session_scope() as session:
        count = (await session.exec(select(func.count()).select_from(User))).one()
        if count:
            return
        if not cfg.admin_password:
            log.warning(
                "Auth is enabled but there are no users and ADMIN_PASSWORD is not set. "
                "Nobody can sign in. Set ADMIN_PASSWORD and restart, or run "
                "`python scripts/create_user.py <username>`."
            )
            return
        try:
            user = await create_user(session, cfg.admin_username, cfg.admin_password)
        except ValueError as exc:
            # Startup must not silently continue with no way to sign in.
            raise RuntimeError(f"Could not create the bootstrap admin: {exc}") from exc
        log.info("Created bootstrap admin user %r", user.username)
