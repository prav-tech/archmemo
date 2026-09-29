"""
Content formatters for Hindsight retain calls.

Each formatter converts a structured data object into rich natural-language
prose that maximises information density for Hindsight's fact extraction.
Keeping formatting logic here makes it easy to iterate on content quality
without touching route handlers or database models.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.decision import Decision, Outcome


def format_decision_for_retain(decision: "Decision") -> str:
    """
    Produce rich natural-language prose for a Decision retain call.

    Includes every structured field so Hindsight can extract facts about
    services, technologies, authors, dates, and the reasoning chain.
    """
    options_text = ""
    if decision.options:
        opts = "\n".join(f"  - {o}" for o in decision.options)
        options_text = f"\nOptions considered:\n{opts}"

    tags_text = ", ".join(decision.tags) if decision.tags else "none"
    services_text = ", ".join(decision.services) if decision.services else "none"
    related_text = (
        ", ".join(decision.related_decisions) if decision.related_decisions else "none"
    )

    return f"""Architecture Decision Record [{decision.decision_id}]: {decision.title}

Decision ID: {decision.decision_id}
Date: {decision.date}
Authors: {decision.authors}
Domain: {decision.domain}
Services affected: {services_text}
Status: {decision.status}
Tags: {tags_text}
Related decisions: {related_text}

Context and problem statement:
{decision.context}

Forces and constraints:
{decision.forces or 'Not specified'}
{options_text}

Chosen option: {decision.chosen_option}

Rationale:
{decision.rationale}

Expected outcomes:
{decision.expected_outcomes or 'Not specified'}
"""


def format_outcome_for_retain(decision: "Decision", outcome: "Outcome") -> str:
    """
    Produce rich natural-language prose for an Outcome retain call.

    References the original decision_id explicitly so Hindsight can link
    the outcome facts to the decision facts during recall.
    """
    metrics_text = ""
    if outcome.metrics:
        lines = [f"  - {k}: {v}" for k, v in outcome.metrics.items()]
        metrics_text = "\nMeasured metrics:\n" + "\n".join(lines)

    repeat_text = "Yes" if outcome.would_repeat else "No"
    regret_label = _regret_label(outcome.regret_score)

    return f"""Outcome Update for Architecture Decision [{decision.decision_id}]: {decision.title}

Decision ID: {decision.decision_id}
Outcome recorded at: {outcome.recorded_at}
Recorded by: {outcome.recorded_by or 'unknown'}

Actual results:
{outcome.actual_results}
{metrics_text}

Incidents caused or related: {outcome.incidents or 'None reported'}

Regret score: {outcome.regret_score}/5 ({regret_label})
Would repeat this decision: {repeat_text}

Lessons learned:
{outcome.lessons}

Original expected outcomes were: {decision.expected_outcomes or 'Not specified'}
Original rationale was: {decision.rationale}
"""


def _regret_label(score: int) -> str:
    labels = {
        1: "No regret – strong success",
        2: "Minor regret – mostly worked",
        3: "Moderate regret – mixed results",
        4: "Significant regret – would reconsider",
        5: "Strong regret – clear mistake in hindsight",
    }
    return labels.get(score, "Unknown")


# ── Tags / metadata / ids ─────────────────────────────────────────────────
#
# Hindsight tags are what make recall filterable (domain, service, year,
# severity, ...). metadata + document_id make every recalled fact traceable
# back to the SQL record. Content prose alone is NOT enough for that:
# Hindsight extracts facts from prose and may drop the ID.


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", value.strip().lower()).strip("-")


def outcome_severity(regret_score: int) -> str:
    """Map the 1-5 regret score onto a coarse filterable severity tag."""
    if regret_score >= 4:
        return "high"
    if regret_score == 3:
        return "medium"
    return "low"


def decision_document_id(decision_id: str) -> str:
    """Stable document id so re-retaining a decision upserts rather than duplicates."""
    return decision_id


def outcome_document_id(decision_id: str, outcome_id: int | None) -> str:
    return f"{decision_id}:outcome:{outcome_id}"


def decision_tags(decision: "Decision") -> list[str]:
    tags = [
        "kind:decision",
        f"decision:{decision.decision_id}",
        f"domain:{_slug(decision.domain)}",
        f"year:{decision.date[:4]}",
        f"status:{_slug(decision.status)}",
    ]
    tags += [f"service:{_slug(s)}" for s in decision.services or []]
    tags += [f"tag:{_slug(t)}" for t in decision.tags or []]
    return list(dict.fromkeys(tags))


def outcome_tags(decision: "Decision", outcome: "Outcome") -> list[str]:
    tags = decision_tags(decision)
    tags[0] = "kind:outcome"
    tags += [
        f"outcome_severity:{outcome_severity(outcome.regret_score)}",
        f"would_repeat:{'yes' if outcome.would_repeat else 'no'}",
    ]
    return list(dict.fromkeys(tags))


def decision_metadata(decision: "Decision") -> dict[str, str]:
    """Hindsight metadata values must be strings."""
    return {
        "decision_id": decision.decision_id,
        "kind": "decision",
        "domain": decision.domain,
        "date": decision.date,
        "status": decision.status,
    }


def outcome_metadata(decision: "Decision", outcome: "Outcome") -> dict[str, str]:
    return {
        "decision_id": decision.decision_id,
        "kind": "outcome",
        "domain": decision.domain,
        "regret_score": str(outcome.regret_score),
        "outcome_severity": outcome_severity(outcome.regret_score),
        "would_repeat": str(outcome.would_repeat).lower(),
    }


def as_utc(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; Hindsight wants an unambiguous timestamp."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_decision_date(date_str: str) -> datetime:
    return as_utc(datetime.fromisoformat(date_str))
