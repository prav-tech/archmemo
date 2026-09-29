"""
Unit tests for app.auth.security. No app, database or network involved.
"""

from __future__ import annotations

import time

import jwt

from app.auth.security import (
    LoginThrottle,
    auth_config_problems,
    create_access_token,
    decode_access_token,
    dummy_hash,
    hash_password,
    validate_new_password,
    verify_password,
)

SECRET = "s" * 40


# ── passwords ─────────────────────────────────────────────────────────────


def test_hash_round_trip_and_salting():
    h1, h2 = hash_password("correct horse battery"), hash_password("correct horse battery")
    assert h1 != h2                                   # per-hash random salt
    assert verify_password("correct horse battery", h1)
    assert verify_password("correct horse battery", h2)
    assert not verify_password("correct horse batterx", h1)
    assert h1.startswith("scrypt$")


def test_verify_never_raises_on_garbage():
    for bad in ["", "plaintext", "scrypt$a$b$c$d$e", "bcrypt$1$2$3$4$5", "scrypt$16384$8$1$!!$!!", "$" * 5]:
        assert verify_password("anything", bad) is False


def test_dummy_hash_is_valid_but_unguessable():
    assert dummy_hash() == dummy_hash()               # cached
    assert not verify_password("", dummy_hash())
    assert not verify_password("password", dummy_hash())


def test_password_policy():
    assert validate_new_password("short") is not None
    assert validate_new_password("x" * 10) is None
    assert validate_new_password("x" * 257) is not None


# ── tokens ────────────────────────────────────────────────────────────────


def _mint(**kw):
    args = dict(secret=SECRET, algorithm="HS256", expires_minutes=60)
    args.update(kw)
    return create_access_token("alice", **args)


def test_token_round_trip():
    assert decode_access_token(_mint(), secret=SECRET, algorithm="HS256") == "alice"


def test_expired_token_is_rejected():
    long_ago = time.time() - 3 * 3600
    token = _mint(now=long_ago, expires_minutes=60)
    assert decode_access_token(token, secret=SECRET, algorithm="HS256") is None


def test_wrong_secret_and_tampering_are_rejected():
    token = _mint()
    assert decode_access_token(token, secret="t" * 40, algorithm="HS256") is None
    head, body, sig = token.split(".")
    assert decode_access_token(f"{head}.{body}x.{sig}", secret=SECRET, algorithm="HS256") is None
    assert decode_access_token("not-a-jwt", secret=SECRET, algorithm="HS256") is None
    assert decode_access_token("", secret=SECRET, algorithm="HS256") is None


def test_alg_none_and_algorithm_swap_are_rejected():
    claims = {"sub": "alice", "iat": int(time.time()), "exp": int(time.time()) + 600}
    unsigned = jwt.encode(claims, key="", algorithm="none")
    assert decode_access_token(unsigned, secret=SECRET, algorithm="HS256") is None
    hs512 = jwt.encode(claims, SECRET, algorithm="HS512")   # valid signature, wrong algorithm
    assert decode_access_token(hs512, secret=SECRET, algorithm="HS256") is None


def test_token_missing_required_claims_is_rejected():
    now = int(time.time())
    for claims in (
        {"iat": now, "exp": now + 600},                     # no sub
        {"sub": "alice", "iat": now},                       # no exp: would never expire
        {"sub": "alice", "exp": now + 600},                 # no iat
        {"sub": "", "iat": now, "exp": now + 600},          # empty sub
    ):
        token = jwt.encode(claims, SECRET, algorithm="HS256")
        assert decode_access_token(token, secret=SECRET, algorithm="HS256") is None


# ── config check ──────────────────────────────────────────────────────────


def test_auth_config_problems():
    assert auth_config_problems(secret=SECRET, algorithm="HS256") == []
    assert auth_config_problems(secret="", algorithm="HS256")
    assert auth_config_problems(secret="change-me-to-a-very-long-random-string-in-production", algorithm="HS256")
    assert auth_config_problems(secret="tooshort", algorithm="HS256")
    assert auth_config_problems(secret=SECRET, algorithm="none")
    assert auth_config_problems(secret=SECRET, algorithm="RS256")


# ── login throttle ────────────────────────────────────────────────────────


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_throttle_locks_after_max_failures_and_expires():
    clock = Clock()
    th = LoginThrottle(max_failures=3, window_seconds=300, clock=clock)
    for _ in range(2):
        th.record_failure("alice")
    assert th.retry_after("alice") == 0
    th.record_failure("alice")
    assert th.retry_after("alice") == 300
    clock.t += 100
    assert th.retry_after("alice") == 200
    assert th.retry_after("bob") == 0                       # other accounts unaffected
    clock.t += 201
    assert th.retry_after("alice") == 0                     # window elapsed


def test_throttle_reset_on_success():
    th = LoginThrottle(max_failures=2, window_seconds=60, clock=Clock())
    th.record_failure("alice")
    th.record_failure("alice")
    assert th.retry_after("alice") > 0
    th.reset("alice")
    assert th.retry_after("alice") == 0


def test_throttle_memory_is_bounded():
    clock = Clock()
    th = LoginThrottle(max_failures=5, window_seconds=60, clock=clock)
    th._MAX_TRACKED_KEYS = 50
    for i in range(500):
        th.record_failure(f"user{i}")
    assert len(th._failures) <= 50
