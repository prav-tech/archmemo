"""
Authentication and access control, exercised through the real app.

The suite default is AUTH_ENABLED=false (see conftest). The `auth_on` fixture
switches it on for a test and creates the user alice.
"""

from __future__ import annotations

import time

import pytest
import pytest_asyncio

from app.auth.security import create_access_token
from app.auth.service import create_user, ensure_bootstrap_admin
from app.config import get_settings
from app.db import session_scope
from app.models.user import User
from app.routes.auth import get_login_throttle
from tests.test_memory_loop import DECISION, OUTCOME, PROPOSAL

SECRET = "k" * 48
PASSWORD = "correct-horse-battery"


@pytest_asyncio.fixture
async def auth_on(client, monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "auth_enabled", True)
    monkeypatch.setattr(cfg, "jwt_secret_key", SECRET)
    monkeypatch.setattr(cfg, "jwt_algorithm", "HS256")
    monkeypatch.setattr(cfg, "login_max_failures", 3)
    get_login_throttle.cache_clear()
    async with session_scope() as s:
        await create_user(s, "alice", PASSWORD)
    yield cfg
    get_login_throttle.cache_clear()


async def _login(client, username="alice", password=PASSWORD):
    return await client.post("/api/auth/login", json={"username": username, "password": password})


# ── access control ────────────────────────────────────────────────────────


async def test_every_data_route_requires_a_session(client, auth_on, llm):
    for path in ("/api/decisions", "/api/decisions/DEC-2024-001", "/api/decisions/missing-outcomes",
                 "/api/decisions/DEC-2024-001/outcomes", "/api/decisions/DEC-2024-001/export",
                 "/api/audit", "/api/audit/1", "/api/auth/me"):
        r = await client.get(path)
        assert r.status_code == 401, path
        assert r.headers["www-authenticate"] == "Bearer"
    for path, body in (("/api/decisions", DECISION), ("/api/briefing", {"proposal": PROPOSAL}),
                       ("/api/decisions/DEC-2024-001/outcomes", OUTCOME)):
        assert (await client.post(path, json=body)).status_code == 401, path
    assert (await client.post("/api/decisions/DEC-2024-001/resync")).status_code == 401
    assert (await client.patch("/api/decisions/DEC-2024-001", json={"status": "deprecated"})).status_code == 401
    assert llm.calls == 0                                   # an unauthenticated briefing never reaches the model


async def test_health_and_login_are_reachable_signed_out(client, auth_on):
    assert (await client.get("/api/health")).status_code == 200
    assert (await _login(client, password="wrong-password-here")).status_code == 401


# ── login ─────────────────────────────────────────────────────────────────


async def test_login_sets_httponly_cookie_and_session_works(client, auth_on):
    r = await _login(client)
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "alice" and body["auth_enabled"] is True
    assert body["token_type"] == "bearer" and body["expires_in"] == auth_on.jwt_expire_minutes * 60

    cookie = r.headers["set-cookie"].lower()
    assert f"{auth_on.auth_cookie_name}=" in cookie
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    assert "; secure" not in cookie                          # AUTH_COOKIE_SECURE defaults to false

    assert (await client.get("/api/decisions")).status_code == 200      # cookie jar carries the session
    assert (await client.get("/api/auth/me")).json() == {"username": "alice", "auth_enabled": True}


async def test_secure_flag_follows_setting(client, auth_on, monkeypatch):
    monkeypatch.setattr(auth_on, "auth_cookie_secure", True)
    assert "; secure" in (await _login(client)).headers["set-cookie"].lower()


async def test_username_is_case_insensitive(client, auth_on):
    assert (await _login(client, username="  ALICE ")).status_code == 200


async def test_unknown_user_and_wrong_password_are_indistinguishable(client, auth_on):
    wrong = await _login(client, password="wrong-password-here")
    unknown = await _login(client, username="mallory", password="wrong-password-here")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_repeated_failures_lock_the_account_even_for_the_right_password(client, auth_on):
    for _ in range(3):
        assert (await _login(client, password="wrong-password-here")).status_code == 401
    locked = await _login(client)                            # correct password, still refused
    assert locked.status_code == 429
    assert int(locked.headers["retry-after"]) > 0
    assert (await _login(client, username="someone-else")).status_code == 401   # other accounts unaffected


async def test_successful_login_clears_the_failure_count(client, auth_on):
    for _ in range(2):
        await _login(client, password="wrong-password-here")
    assert (await _login(client)).status_code == 200
    for _ in range(2):
        assert (await _login(client, password="wrong-password-here")).status_code == 401
    assert (await _login(client)).status_code == 200         # never reached the limit of 3


# ── tokens ────────────────────────────────────────────────────────────────


async def test_bearer_token_works_without_the_cookie(client, auth_on):
    token = (await _login(client)).json()["access_token"]
    client.cookies.clear()
    assert (await client.get("/api/decisions")).status_code == 401
    ok = await client.get("/api/decisions", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200


async def test_logout_clears_the_session(client, auth_on):
    await _login(client)
    assert (await client.get("/api/decisions")).status_code == 200
    assert (await client.post("/api/auth/logout")).status_code == 200
    assert (await client.get("/api/decisions")).status_code == 401


async def test_bad_tokens_are_rejected(client, auth_on):
    def bearer(t):
        return {"Authorization": f"Bearer {t}"}

    expired = create_access_token("alice", secret=SECRET, algorithm="HS256",
                                  expires_minutes=5, now=time.time() - 3600)
    forged = create_access_token("alice", secret="z" * 48, algorithm="HS256", expires_minutes=5)
    for token in (expired, forged, "garbage"):
        assert (await client.get("/api/decisions", headers=bearer(token))).status_code == 401


async def test_valid_token_for_deleted_or_disabled_user_is_rejected(client, auth_on):
    token = create_access_token("ghost", secret=SECRET, algorithm="HS256", expires_minutes=5)
    assert (await client.get("/api/decisions", headers={"Authorization": f"Bearer {token}"})).status_code == 401

    await _login(client)
    assert (await client.get("/api/decisions")).status_code == 200
    async with session_scope() as s:
        from app.auth.service import get_user_by_username
        user = await get_user_by_username(s, "alice")
        user.is_active = False
        s.add(user)
        await s.commit()
    assert (await client.get("/api/decisions")).status_code == 401        # takes effect immediately
    assert (await _login(client)).status_code == 401                      # and cannot sign back in


# ── identity is attributed server-side ────────────────────────────────────


async def test_briefing_audit_records_the_signed_in_user_not_the_payload(client, auth_on, llm):
    await _login(client)
    r = await client.post("/api/decisions", json=DECISION)
    assert r.status_code == 201, r.text
    llm.reply = "ok"
    body = (await client.post("/api/briefing", json={"proposal": PROPOSAL, "requested_by": "mallory"})).json()
    audit = (await client.get(f"/api/audit/{body['audit_id']}")).json()
    assert audit["requested_by"] == "alice"


async def test_outcome_recorded_by_defaults_to_user_but_respects_a_named_team(client, auth_on):
    await _login(client)
    dec_id = (await client.post("/api/decisions", json=DECISION)).json()["decision_id"]
    without = {k: v for k, v in OUTCOME.items() if k != "recorded_by"}
    a = (await client.post(f"/api/decisions/{dec_id}/outcomes", json=without)).json()
    b = (await client.post(f"/api/decisions/{dec_id}/outcomes", json=OUTCOME)).json()
    assert a["recorded_by"] == "alice" and b["recorded_by"] == "sre-team"


# ── auth disabled ─────────────────────────────────────────────────────────


async def test_auth_disabled_mode_is_open_and_says_so(client):
    assert (await client.get("/api/decisions")).status_code == 200
    me = (await client.get("/api/auth/me")).json()
    assert me == {"username": "anonymous", "auth_enabled": False}
    assert (await _login(client)).status_code == 400


async def test_auth_disabled_keeps_client_supplied_requested_by(client, llm):
    await client.post("/api/decisions", json=DECISION)
    llm.reply = "ok"
    body = (await client.post("/api/briefing", json={"proposal": PROPOSAL, "requested_by": "cli-user"})).json()
    assert (await client.get(f"/api/audit/{body['audit_id']}")).json()["requested_by"] == "cli-user"


# ── startup ───────────────────────────────────────────────────────────────


async def test_startup_refuses_unsafe_auth_settings(monkeypatch):
    from app.main import app, lifespan
    cfg = get_settings()
    monkeypatch.setattr(cfg, "auth_enabled", True)
    monkeypatch.setattr(cfg, "jwt_secret_key", "")
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        async with lifespan(app):
            pass


async def test_bootstrap_admin_only_on_an_empty_users_table(client, monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "auth_enabled", True)
    monkeypatch.setattr(cfg, "admin_username", "Root")
    monkeypatch.setattr(cfg, "admin_password", "bootstrap-password-1")
    await ensure_bootstrap_admin()
    async with session_scope() as s:
        from sqlmodel import select
        users = list((await s.exec(select(User))).all())
        assert [u.username for u in users] == ["root"]          # normalised

    monkeypatch.setattr(cfg, "admin_username", "someone-else")
    await ensure_bootstrap_admin()                              # users exist: no-op
    async with session_scope() as s:
        from sqlmodel import select
        assert len((await s.exec(select(User))).all()) == 1


async def test_bootstrap_rejects_a_weak_admin_password(client, monkeypatch):
    cfg = get_settings()
    monkeypatch.setattr(cfg, "auth_enabled", True)
    monkeypatch.setattr(cfg, "admin_password", "short")
    with pytest.raises(RuntimeError, match="bootstrap admin"):
        await ensure_bootstrap_admin()
