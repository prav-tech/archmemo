"""
Test harness: real FastAPI app + real SQL (temp SQLite), with the two external
systems replaced by deterministic fakes:

* FakeMemory  – in-memory stand-in for Hindsight with the same async interface
                as app.memory.client.MemoryClient (retain_* / recall_for_briefing).
* fake LLM    – scripted `complete_chat`, so tests can assert on the exact prompt
                the model received and simulate hallucinated citations.
"""

from __future__ import annotations

import os
import re
import tempfile

_DB = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_DB}"
os.environ["LLM_API_KEY"] = "test"
# The existing suite exercises the API directly. Auth tests switch it on per test
# (see tests/test_auth.py), so everything else keeps running unauthenticated.
os.environ["AUTH_ENABLED"] = "false"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

import app.memory.client as memory_client_module  # noqa: E402
from app.db import create_db_and_tables, get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.memory.client import RecalledMemory  # noqa: E402
from app.memory.content import (  # noqa: E402
    decision_tags,
    format_decision_for_retain,
    format_outcome_for_retain,
    outcome_tags,
)

_WORD = re.compile(r"[a-z0-9]+")


class FakeMemory:
    """Keyword-overlap 'semantic' recall over retained facts, with tag filtering."""

    def __init__(self) -> None:
        self.records: dict[str, dict] = {}   # document_id -> record (upsert semantics)
        self.fail_retain = False
        self.fail_recall = False

    async def retain_decision(self, decision) -> None:
        if self.fail_retain:
            raise ConnectionError("hindsight down")
        self.records[decision.decision_id] = {
            "decision_id": decision.decision_id, "kind": "decision",
            "text": format_decision_for_retain(decision), "tags": decision_tags(decision),
        }

    async def retain_outcome(self, decision, outcome) -> None:
        if self.fail_retain:
            raise ConnectionError("hindsight down")
        self.records[f"{decision.decision_id}:outcome:{outcome.id}"] = {
            "decision_id": decision.decision_id, "kind": "outcome",
            "text": format_outcome_for_retain(decision, outcome),
            "tags": outcome_tags(decision, outcome),
        }

    async def recall_for_briefing(self, query, top_k=None, domain=None, services=None):
        if self.fail_recall:
            raise ConnectionError("hindsight down")
        wanted = ([f"domain:{domain.lower()}"] if domain else []) + [
            f"service:{s.lower()}" for s in services or []
        ]
        q = set(_WORD.findall(query.lower()))
        scored = []
        for doc_id, r in self.records.items():
            if wanted and not set(wanted) & set(r["tags"]):
                continue
            overlap = len(q & set(_WORD.findall(r["text"].lower())))
            if overlap >= 3:
                scored.append((overlap, doc_id, r))
        scored.sort(key=lambda t: -t[0])
        return [
            RecalledMemory(memory_id=d, text=r["text"], decision_id=r["decision_id"],
                           kind=r["kind"], score=float(o), tags=r["tags"])
            for o, d, r in scored[: top_k or 15]
        ]


@pytest_asyncio.fixture
async def memory(monkeypatch):
    fake = FakeMemory()
    monkeypatch.setattr(memory_client_module, "_memory_client", fake)
    return fake


@pytest_asyncio.fixture
async def client(memory):
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await create_db_and_tables()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def llm(monkeypatch):
    """Scripted LLM. `llm.reply` is the text returned; `llm.prompts` records user prompts."""
    import app.routes.briefing as briefing_module

    class Script:
        reply = ""
        calls = 0
        prompts: list[str] = []

    s = Script()
    s.prompts = []

    async def fake_complete(system: str, user: str):
        s.calls += 1
        s.prompts.append(user)
        return s.reply, "fake-model"

    monkeypatch.setattr(briefing_module, "complete_chat", fake_complete)
    return s
