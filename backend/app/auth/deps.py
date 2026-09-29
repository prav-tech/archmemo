"""FastAPI dependency that protects routes."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.security import decode_access_token
from app.auth.service import get_user_by_username
from app.config import get_settings
from app.db import get_session

# auto_error=False so a missing header falls through to the session cookie
# instead of FastAPI answering 403 on its own.
_bearer = HTTPBearer(auto_error=False)

ANONYMOUS = "anonymous"


@dataclass(frozen=True)
class CurrentUser:
    username: str
    # True only when AUTH_ENABLED=false. Callers must then not trust the identity.
    anonymous: bool = False


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    """
    Resolve the caller from `Authorization: Bearer <jwt>` or the session cookie.

    A valid signature is not enough: the account must still exist and be active,
    so deleting or disabling a user takes effect on their next request.
    """
    cfg = get_settings()
    if not cfg.auth_enabled:
        return CurrentUser(username=ANONYMOUS, anonymous=True)

    token = credentials.credentials if credentials else request.cookies.get(cfg.auth_cookie_name)
    if not token:
        raise _unauthorized()

    username = decode_access_token(token, secret=cfg.jwt_secret_key, algorithm=cfg.jwt_algorithm)
    if not username:
        raise _unauthorized()

    user = await get_user_by_username(session, username)
    if user is None or not user.is_active:
        raise _unauthorized()
    return CurrentUser(username=user.username)
