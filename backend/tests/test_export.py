"""Unit tests for the markdown export (pure function, no app needed)."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

from app.export import render_decision_markdown


def _decision(**over):
    base = dict(
        decision_id="DEC-2024-001", title="Adopt Kafka", date="2024-01-15", authors="Priya Nair",
        domain="platform", services=["order-service", "inventory-service"], status="active",
        context="Polling caused stale reads.", forces="High throughput.",
        options=["Kafka", "RabbitMQ"], chosen_option="Kafka", rationale="Durable log and replay.",
        expected_outcomes="Sub-100ms delivery.", tags=["kafka"], related_decisions=["DEC-2023-004"],
    )
    base.update(over)
    return SimpleNamespace(**base)


def _outcome(**over):
    base = dict(
        regret_score=4, would_repeat=False, actual_results="Latency fell but lag stuck orders.",
        incidents="Partition caused stuck orders.", lessons="Alert on consumer lag.",
        metrics={"p99_ms": 89, "replay_supported": True, "by_region": {"eu": 1}},
        recorded_at=datetime(2025, 3, 1, 10, 30), recorded_by="sre-team",
    )
    base.update(over)
    return SimpleNamespace(**base)


TODAY = date(2026, 9, 29)


def test_metadata_is_a_list_so_markdown_does_not_collapse_it():
    md = render_decision_markdown(_decision(), [], generated_on=TODAY)
    assert "- **Date:** 2024-01-15\n- **Authors:** Priya Nair\n" in md
    assert "- **Services:** order-service, inventory-service" in md


def test_chosen_option_is_marked_once():
    md = render_decision_markdown(_decision(), [], generated_on=TODAY)
    assert "- Kafka **(chosen)**" in md and md.count("(chosen)") == 1
    assert "- RabbitMQ\n" in md


def test_export_includes_outcomes_with_scores_lessons_and_metrics():
    md = render_decision_markdown(_decision(), [_outcome()], generated_on=TODAY)
    assert "## Recorded outcomes" in md
    assert "### Outcome 1: recorded 2025-03-01 by sre-team" in md
    assert "**Regret score:** 4/5" in md
    assert "**Would repeat this decision:** no" in md
    assert "Alert on consumer lag." in md and "Partition caused stuck orders." in md
    assert "- **p99_ms:** 89" in md
    assert "- **replay_supported:** yes" in md              # booleans are readable
    assert '- **by_region:** {"eu": 1}' in md               # nested values stay valid JSON


def test_multiple_outcomes_are_numbered_in_order():
    md = render_decision_markdown(_decision(), [_outcome(), _outcome(regret_score=2)], generated_on=TODAY)
    assert md.index("### Outcome 1") < md.index("### Outcome 2")
    assert "2 recorded." in md


def test_no_outcome_says_so_plainly():
    md = render_decision_markdown(_decision(), [], generated_on=TODAY)
    assert "No outcome has been recorded yet" in md
    assert "### Outcome" not in md


def test_optional_fields_are_omitted_or_defaulted():
    d = _decision(forces=None, options=[], expected_outcomes=None, tags=[], services=[], related_decisions=[])
    o = _outcome(incidents=None, metrics=None, recorded_by=None)
    md = render_decision_markdown(d, [o], generated_on=TODAY)
    assert md.count("_Not specified_") == 3
    assert "#### Incidents" not in md and "#### Measured" not in md
    assert "recorded 2025-03-01\n" in md                     # no dangling " by "


def test_footer_uses_the_supplied_date():
    md = render_decision_markdown(_decision(), [], generated_on=TODAY)
    assert md.rstrip().endswith("_Exported from ArchMemory on 2026-09-29_")
