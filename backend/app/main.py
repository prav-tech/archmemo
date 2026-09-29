"""
ArchMemory FastAPI application entry point.

Startup order (see `lifespan`):
1. Refuse to start with unsafe auth settings.
2. Create SQLite tables.
3. Create the bootstrap admin on first run.

Access control: every router below is mounted with `require_user`, except the
auth router (login/logout must be reachable when signed out) and /api/health.
Enforcement lives here in the API, not in the frontend, so it holds no matter
which client is calling.
"""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.deps import require_user
from app.auth.security import auth_config_problems
from app.auth.service import ensure_bootstrap_admin
from app.config import get_settings
from app.db import create_db_and_tables

# Import models so SQLModel metadata is populated before table creation
from app.models import decision, user  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s – %(message)s",
)

log = logging.getLogger(__name__)
cfg = get_settings()

# Accept a caller-supplied request ID only if it is short and boring; it ends up
# in log lines, so anything else (newlines, control characters) is replaced.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if cfg.auth_enabled:
        problems = auth_config_problems(secret=cfg.jwt_secret_key, algorithm=cfg.jwt_algorithm)
        if problems:
            raise RuntimeError(
                "Refusing to start with unsafe auth settings:\n  - "
                + "\n  - ".join(problems)
                + '\nGenerate a secret with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
                + "\n(Set AUTH_ENABLED=false only for local experiments.)"
            )
    else:
        log.warning("AUTH_ENABLED=false: the API is open to anyone who can reach it.")

    log.info("Creating database tables…")
    await create_db_and_tables()
    await ensure_bootstrap_admin()
    log.info("ArchMemory API ready.")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=cfg.app_name,
        description="Architecture Decision & Outcome Memory Agent",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request IDs + unhandled-error handling ────────────────────────────
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        supplied = request.headers.get("x-request-id", "")
        request_id = supplied if _SAFE_REQUEST_ID.match(supplied) else uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        # Expected failures (validation, 401/404, Hindsight/LLM outages) are raised
        # as HTTPException and never reach here. This is the "we did not expect
        # this" path: log the traceback once, tell the client only a reference.
        request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex[:12]
        log.exception("Unhandled error [%s] %s %s", request_id, request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    # ── Routers ───────────────────────────────────────────────────────────
    from app.routes import audit, auth, briefing, decisions, missing_outcomes, outcomes

    protected = [Depends(require_user)]

    app.include_router(auth.router, prefix="/api", tags=["auth"])

    # missing_outcomes registered before decisions to prevent /decisions/{id}
    # from catching the static /decisions/missing-outcomes path.
    app.include_router(
        missing_outcomes.router, prefix="/api", tags=["decisions"], dependencies=protected
    )
    app.include_router(
        decisions.router, prefix="/api/decisions", tags=["decisions"], dependencies=protected
    )
    app.include_router(
        outcomes.router, prefix="/api/decisions", tags=["outcomes"], dependencies=protected
    )
    app.include_router(briefing.router, prefix="/api", tags=["briefing"], dependencies=protected)
    app.include_router(audit.router, prefix="/api", tags=["audit"], dependencies=protected)

    @app.get("/api/health", tags=["health"])
    async def health() -> dict:
        return {"status": "ok", "service": cfg.app_name}

    return app


app = create_app()
