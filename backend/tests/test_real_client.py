"""
Exercise the REAL MemoryClient against the real hindsight-client SDK types.
Only the network call is stubbed, so signature drift or a wrong kwarg fails here.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from hindsight_client import Hindsight
from hindsight_client_api.models.recall_response import RecallResponse
from hindsight_client_api.models.recall_result import RecallResult

from app.memory.client import MemoryClient, _attribute
from app.models.decision import Decision, Outcome


def _decision() -> Decision:
    return Decision(
        decision_id="DEC-2024-001", title="Adopt Kafka", date="2024-01-15", authors="A B",
        domain="Platform", services=["order-service"], context="c" * 30,
        chosen_option="Kafka", rationale="r" * 30, tags=["Kafka"],
    )


def _outcome() -> Outcome:
    return Outcome(id=7, decision_id="DEC-2024-001", actual_results="a" * 30, regret_score=4,
                   lessons="l" * 12, would_repeat=False,
                   recorded_at=datetime(2025, 3, 1))  # naive, as SQLite returns it


@pytest.fixture
def mc():
    c = MemoryClient()
    calls: dict[str, dict] = {}

    async def aretain(**kw):
        inspect.signature(Hindsight.aretain).bind(c._client, **kw)   # raises TypeError on drift
        calls["retain"] = kw

    async def arecall(**kw):
        inspect.signature(Hindsight.arecall).bind(c._client, **kw)
        calls["recall"] = kw
        return RecallResponse(results=[
            RecallResult(id="1", text="Kafka chosen for order events", document_id="DEC-2024-001",
                         metadata={"decision_id": "DEC-2024-001", "kind": "decision"}),
            RecallResult(id="2", text="Consumer lag caused stuck orders",
                         document_id="DEC-2024-001:outcome:7", tags=["kind:outcome", "decision:DEC-2024-001"]),
            RecallResult(id="3", text="Mentions DEC-2023-009 only once"),
            RecallResult(id="4", text="Compares DEC-2023-009 with DEC-2022-002"),
            RecallResult(id="5", text="No ids at all"),
        ])

    c._client.aretain, c._client.arecall = aretain, arecall
    c.calls = calls
    return c


async def test_retain_decision_sends_id_tags_metadata_and_timestamp(mc):
    await mc.retain_decision(_decision())
    kw = mc.calls["retain"]
    assert kw["document_id"] == "DEC-2024-001"
    assert kw["metadata"] == {"decision_id": "DEC-2024-001", "kind": "decision",
                              "domain": "Platform", "date": "2024-01-15", "status": "active"}
    assert {"kind:decision", "decision:DEC-2024-001", "domain:platform", "year:2024",
            "service:order-service", "tag:kafka"} <= set(kw["tags"])
    assert kw["timestamp"] == datetime(2024, 1, 15, tzinfo=timezone.utc)
    assert all(isinstance(v, str) for v in kw["metadata"].values())


async def test_retain_outcome_is_a_separate_document_with_severity(mc):
    await mc.retain_outcome(_decision(), _outcome())
    kw = mc.calls["retain"]
    assert kw["document_id"] == "DEC-2024-001:outcome:7"
    assert "outcome_severity:high" in kw["tags"] and "kind:outcome" in kw["tags"]
    assert "kind:decision" not in kw["tags"]
    assert kw["metadata"]["regret_score"] == "4"
    assert kw["timestamp"].tzinfo is not None


async def test_recall_attribution_and_filters(mc):
    mems = await mc.recall_for_briefing("q" * 5000, top_k=10, domain="Platform", services=["Order Service"])
    kw = mc.calls["recall"]
    assert kw["tags"] == ["domain:platform", "service:order-service"] and kw["tags_match"] == "any_strict"
    assert len(kw["query"]) == 2000                       # long proposals are truncated
    assert [(m.decision_id, m.kind) for m in mems] == [
        ("DEC-2024-001", "decision"),   # via metadata
        ("DEC-2024-001", "outcome"),    # via document_id / tags
        ("DEC-2023-009", "unknown"),    # single unambiguous ID in text
        (None, "unknown"),              # two IDs in text -> refuse to guess
        (None, "unknown"),
    ]


async def test_recall_without_filters_sends_no_tags(mc):
    await mc.recall_for_briefing("proposal text")
    assert "tags" not in mc.calls["recall"]


def test_attribute_prefers_metadata_over_text():
    r = SimpleNamespace(metadata={"decision_id": "DEC-2024-001", "kind": "outcome"},
                        tags=[], document_id="", text="see DEC-2020-999")
    assert _attribute(r) == ("DEC-2024-001", "outcome")
