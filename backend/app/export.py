"""
Markdown export of a decision and its recorded outcomes.

Pure function over plain attributes (no database or FastAPI imports) so it can
be unit tested with simple stand-in objects.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.decision import Decision, Outcome

_NONE = "_Not specified_"


def _fmt_metric(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _fmt_day(value: datetime | date | str | None) -> str:
    if value is None:
        return "unknown date"
    if isinstance(value, str):
        return value[:10]
    return value.strftime("%Y-%m-%d")


def _render_outcome(o: "Outcome", index: int) -> str:
    who = f" by {o.recorded_by}" if o.recorded_by else ""
    lines = [
        f"### Outcome {index}: recorded {_fmt_day(o.recorded_at)}{who}",
        "",
        f"- **Regret score:** {o.regret_score}/5 (1 = no regret, 5 = strong regret)",
        f"- **Would repeat this decision:** {'yes' if o.would_repeat else 'no'}",
        "",
        "#### What happened",
        "",
        o.actual_results,
        "",
    ]
    if o.incidents:
        lines += ["#### Incidents", "", o.incidents, ""]
    lines += ["#### Lessons", "", o.lessons, ""]
    if o.metrics:
        lines += ["#### Measured", ""]
        lines += [f"- **{k}:** {_fmt_metric(v)}" for k, v in o.metrics.items()]
        lines.append("")
    return "\n".join(lines)


def render_decision_markdown(
    decision: "Decision",
    outcomes: Sequence["Outcome"],
    *,
    generated_on: date,
) -> str:
    """Render an ADR plus every recorded outcome as a single Markdown document."""
    d = decision
    # Metadata is a list, not consecutive lines: Markdown collapses single
    # newlines, which would run every field together in one paragraph.
    meta = [
        f"- **Date:** {d.date}",
        f"- **Authors:** {d.authors}",
        f"- **Domain:** {d.domain}",
        f"- **Services:** {', '.join(d.services) if d.services else '_None_'}",
        f"- **Status:** {d.status}",
        f"- **Tags:** {', '.join(d.tags) if d.tags else '_None_'}",
    ]

    if d.options:
        options = "\n".join(
            f"- {o}{' **(chosen)**' if o == d.chosen_option else ''}" for o in d.options
        )
    else:
        options = _NONE

    related = ", ".join(d.related_decisions) if d.related_decisions else "_None_"

    parts = [
        f"# ADR {d.decision_id}: {d.title}",
        "",
        *meta,
        "",
        "## Context",
        "",
        d.context,
        "",
        "## Forces and constraints",
        "",
        d.forces or _NONE,
        "",
        "## Options considered",
        "",
        options,
        "",
        "## Decision",
        "",
        f"**Chosen:** {d.chosen_option}",
        "",
        "## Rationale",
        "",
        d.rationale,
        "",
        "## Expected outcomes",
        "",
        d.expected_outcomes or _NONE,
        "",
        "## Related decisions",
        "",
        related,
        "",
        "## Recorded outcomes",
        "",
    ]

    if outcomes:
        parts.append(f"{len(outcomes)} recorded.")
        parts.append("")
        parts += [_render_outcome(o, i) for i, o in enumerate(outcomes, start=1)]
    else:
        parts += [
            "_No outcome has been recorded yet. Until one is, this decision can be "
            "cited for what was decided but not for how it turned out._",
            "",
        ]

    parts += ["---", "", f"_Exported from ArchMemory on {generated_on:%Y-%m-%d}_", ""]
    return "\n".join(parts)
