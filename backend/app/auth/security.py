"""
Password hashing, session tokens, and login throttling.

This module is deliberately free of FastAPI, SQL and app-settings imports: every
parameter is passed in explicitly, so the security-relevant logic can be unit
tested in isolation (see tests/test_security.py).

Choices worth knowing about
---------------------------
* Passwords use stdlib ``hashlib.scrypt``. There is no third-party hashing
  dependency to drift out of compatibility (passlib 1.7.x breaks against
  bcrypt >= 4.1 / 5.x).
* Tokens are HS* JWTs via PyJWT. The accepted algorithm is fixed by the caller
  and passed to ``decode`` as a one-item allow-list, so a token cannot choose
  its own algorithm (no ``alg: none`` / algorithm confusion).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import math
import secrets
import time
from collections.abc import Callable
from functools import cache

import jwt

# ── Password hashing ──────────────────────────────────────────────────────

# scrypt cost: N=2**14, r=8, p=1 needs ~16 MiB, which is inside OpenSSL's default
# 32 MiB limit and costs roughly 50 ms per hash.
_N, _R, _P, _DKLEN = 2**14, 8, 1, 32
_SCHEME = "scrypt"

MIN_PASSWORD_LENGTH = 10
MAX_PASSWORD_LENGTH = 256


def _b64e(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"), validate=True)


def hash_password(password: str) -> str:
    """Return a self-describing hash: ``scrypt$N$r$p$salt$digest``."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_DKLEN)
    return "$".join([_SCHEME, str(_N), str(_R), str(_P), _b64e(salt), _b64e(digest)])


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check. Malformed or foreign hashes verify as False, never raise."""
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != _SCHEME:
            return False
        expected = _b64d(digest_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_b64d(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


@cache
def dummy_hash() -> str:
    """A valid hash nobody knows the password for.

    Verified against when a username does not exist, so an unknown user and a
    wrong password take about the same time and cannot be told apart.
    """
    return hash_password(secrets.token_urlsafe(16))


def validate_new_password(password: str) -> str | None:
    """Return a human-readable problem with a new password, or None if acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Password must be at most {MAX_PASSWORD_LENGTH} characters."
    return None


# ── Session tokens ────────────────────────────────────────────────────────

ALLOWED_ALGORITHMS = ("HS256", "HS384", "HS512")
_LEEWAY_SECONDS = 10  # tolerate small clock skew between issue and verify


def create_access_token(
    subject: str,
    *,
    secret: str,
    algorithm: str,
    expires_minutes: int,
    now: float | None = None,
) -> str:
    issued = int(time.time() if now is None else now)
    claims = {"sub": subject, "iat": issued, "exp": issued + expires_minutes * 60}
    return jwt.encode(claims, secret, algorithm=algorithm)


def decode_access_token(
    token: str,
    *,
    secret: str,
    algorithm: str,
) -> str | None:
    """Return the token's subject if it is valid and unexpired, otherwise None."""
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
            options={"require": ["exp", "iat", "sub"]},
            leeway=_LEEWAY_SECONDS,
        )
    except jwt.PyJWTError:
        return None
    subject = claims.get("sub")
    return subject if isinstance(subject, str) and subject else None


# ── Configuration check ───────────────────────────────────────────────────

_PLACEHOLDER_SECRETS = {
    "",
    "change-me-in-production-use-a-long-random-string",
    "change-me-to-a-very-long-random-string-in-production",
}
MIN_SECRET_LENGTH = 32


def auth_config_problems(*, secret: str, algorithm: str) -> list[str]:
    """Reasons the auth settings are unsafe to start with (empty list = fine)."""
    problems: list[str] = []
    if secret in _PLACEHOLDER_SECRETS:
        problems.append("JWT_SECRET_KEY is not set (or is still the example placeholder).")
    elif len(secret) < MIN_SECRET_LENGTH:
        problems.append(f"JWT_SECRET_KEY must be at least {MIN_SECRET_LENGTH} characters.")
    if algorithm not in ALLOWED_ALGORITHMS:
        problems.append(f"JWT_ALGORITHM must be one of {', '.join(ALLOWED_ALGORITHMS)}.")
    return problems


# ── Login throttle ────────────────────────────────────────────────────────


class LoginThrottle:
    """
    Lock a username out after repeated failed logins.

    In-process and in-memory: it resets on restart and is not shared between
    workers, which is acceptable for a single-instance internal tool. Failures
    are counted for unknown usernames too, so the throttle does not reveal which
    accounts exist. The trade-off is that someone can lock a known account out
    for one window by failing on purpose.
    """

    _MAX_TRACKED_KEYS = 10_000

    def __init__(
        self,
        max_failures: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_failures
        self._window = window_seconds
        self._clock = clock
        self._failures: dict[str, list[float]] = {}

    def _recent(self, key: str) -> list[float]:
        cutoff = self._clock() - self._window
        recent = [t for t in self._failures.get(key, []) if t > cutoff]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    def retry_after(self, key: str) -> int:
        """Seconds until this key may try again; 0 if it is not locked out."""
        recent = self._recent(key)
        if len(recent) < self._max:
            return 0
        return max(1, math.ceil(recent[0] + self._window - self._clock()))

    def record_failure(self, key: str) -> None:
        if len(self._failures) >= self._MAX_TRACKED_KEYS:
            for k in list(self._failures):  # drop expired entries; bounds memory
                self._recent(k)
            if len(self._failures) >= self._MAX_TRACKED_KEYS:
                self._failures.clear()
        self._failures.setdefault(key, []).append(self._clock())

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
