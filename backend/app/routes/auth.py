"""
Auth routes.

POST /api/auth/login   – exchange username + password for a session
POST /api/auth/logout  – clear the session cookie
GET  /api/auth/me      – who am I (also how the UI learns whether auth is enabled)

Login sets an httpOnly cookie (used by the web UI) and also returns the token in
the body so scripts and the Swagger "Authorize" button can send it as a Bearer
token. The UI never reads the token, so page JavaScript cannot leak it.
"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from app.auth.deps import ANONYMOUS, CurrentUser, require_user
from app.auth.security import (
    MAX_PASSWORD_LENGTH,
    LoginThrottle,
    create_access_token,
    dummy_hash,
    verify_password,
)
from app.auth.service import get_user_by_username, normalize_username
from app.config import get_settings
from app.db import get_session

log = logging.getLogger(__name__)
router = APIRouter()


@lru_cache(maxsize=1)
def get_login_throttle() -> LoginThrottle:
    cfg = get_settings()
    return LoginThrottle(cfg.login_max_failures, cfg.login_lockout_seconds)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=MAX_PASSWORD_LENGTH)


class SessionOut(BaseModel):
    username: str
    auth_enabled: bool


class TokenOut(SessionOut):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


@router.post("/auth/login", response_model=TokenOut)
async def login(
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TokenOut:
    cfg = get_settings()
    if not cfg.auth_enabled:
        raise HTTPException(status_code=400, detail="Authentication is disabled on this server.")

    key = normalize_username(payload.username)
    throttle = get_login_throttle()
    wait = throttle.retry_after(key)
    if wait:
        raise HTTPException(
            status_code=429,
            detail=f"Too many failed sign-in attempts. Try again in {wait} seconds.",
            headers={"Retry-After": str(wait)},
        )

    user = await get_user_by_username(session, key)
    active = user is not None and user.is_active
    # Always run one scrypt verification, even for unknown users, so response
    # time does not reveal which usernames exist. scrypt is CPU-bound, so keep
    # it off the event loop.
    stored = user.password_hash if (user is not None and active) else dummy_hash()
    ok = await asyncio.to_thread(verify_password, payload.password, stored)

    if not (ok and active):
        throttle.record_failure(key)
        log.warning("Failed sign-in for %r", key)
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    throttle.reset(key)
    assert user is not None
    max_age = cfg.jwt_expire_minutes * 60
    token = create_access_token(
        user.username,
        secret=cfg.jwt_secret_key,
        algorithm=cfg.jwt_algorithm,
        expires_minutes=cfg.jwt_expire_minutes,
    )
    response.set_cookie(
        key=cfg.auth_cookie_name,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=cfg.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    log.info("Signed in %r", user.username)
    return TokenOut(
        username=user.username, auth_enabled=True, access_token=token, expires_in=max_age
    )


@router.post("/auth/logout", response_model=dict)
async def logout(response: Response) -> dict:
    """Clear the session cookie. Idempotent; works whether or not a session exists.

    Tokens are stateless, so a copied Bearer token stays valid until it expires.
    """
    cfg = get_settings()
    response.delete_cookie(key=cfg.auth_cookie_name, path="/")
    return {"ok": True}


@router.get("/auth/me", response_model=SessionOut)
async def me(user: CurrentUser = Depends(require_user)) -> SessionOut:
    cfg = get_settings()
    return SessionOut(username=user.username or ANONYMOUS, auth_enabled=cfg.auth_enabled)
