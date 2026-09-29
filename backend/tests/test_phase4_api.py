"""Phase 4 API behaviour outside auth: export, error handling, missing-outcomes age."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from httpx import ASGITransport, AsyncClient

from app.main import app
from tests.test_memory_loop import DECISION, OUTCOME


async def _create(client, **over):
    r = await client.post("/api/decisions", json={**DECISION, **over})
    assert r.status_code == 201, r.text
    return r.json()["decision_id"]


# ── export ────────────────────────────────────────────────────────────────


async def test_export_includes_recorded_outcomes(client):
    dec_id = await _create(client)
    before = (await client.get(f"/api/decisions/{dec_id}/export")).json()["markdown"]
    assert "No outcome has been recorded yet" in before

    await client.post(f"/api/decisions/{dec_id}/outcomes", json=OUTCOME)
    md = (await client.get(f"/api/decisions/{dec_id}/export")).json()["markdown"]
    assert md.startswith(f"# ADR {dec_id}: {DECISION['title']}")
    assert "**Regret score:** 4/5" in md
    assert OUTCOME["lessons"] in md
    assert "- **p99_latency_ms:** 120" in md
    assert "- Apache Kafka **(chosen)**" in md


async def test_export_unknown_decision_is_404(client):
    assert (await client.get("/api/decisions/DEC-2000-001/export")).status_code == 404


# ── request ids and unexpected errors ─────────────────────────────────────


async def test_request_id_is_generated_and_a_safe_one_is_echoed(client):
    generated = (await client.get("/api/health")).headers["x-request-id"]
    assert len(generated) == 12
    echoed = await client.get("/api/health", headers={"X-Request-ID": "trace-abc_123"})
    assert echoed.headers["x-request-id"] == "trace-abc_123"


async def test_unsafe_request_id_is_replaced(client):
    r = await client.get("/api/health", headers={"X-Request-ID": "bad id; DROP"})
    assert r.headers["x-request-id"] != "bad id; DROP" and len(r.headers["x-request-id"]) == 12


async def test_unexpected_error_returns_json_with_reference_and_no_internals(monkeypatch, client):
    import app.routes.decisions as decisions_module

    async def boom(*_a, **_k):
        raise RuntimeError("db password is hunter2")

    monkeypatch.setattr(decisions_module, "_decision_or_404", boom)
    # Starlette re-raises after sending a 500; ask the test transport not to.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/decisions/DEC-2024-001")
    assert r.status_code == 500
    body = r.json()
    assert body["detail"] == "Internal server error"
    assert body["request_id"] == r.headers["x-request-id"]
    assert "hunter2" not in r.text and "Traceback" not in r.text


# ── missing outcomes ──────────────────────────────────────────────────────


async def test_missing_outcomes_reports_age_and_never_goes_negative(client):
    old = (datetime.now(timezone.utc) - timedelta(days=200)).date().isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat()
    old_id = await _create(client, date=old, title="Old decision awaiting an outcome")
    future_id = await _create(client, date=future, title="Future dated decision entry")

    items = (await client.get("/api/decisions/missing-outcomes")).json()
    by_id = {i["decision_id"]: i["days_without_outcome"] for i in items}
    assert by_id[old_id] in (200, 199, 201)                      # tolerate a midnight boundary
    assert by_id[future_id] == 0
    assert [i["decision_id"] for i in items][0] == old_id        # oldest first
