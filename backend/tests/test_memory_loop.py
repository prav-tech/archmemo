"""End-to-end tests for the Decision -> Outcome -> Briefing loop."""

from __future__ import annotations

DECISION = {
    "title": "Adopt Kafka for order event streaming",
    "date": "2024-01-15",
    "authors": "Priya Nair",
    "domain": "platform",
    "services": ["order-service", "inventory-service"],
    "context": "Polling based integration between order service and inventory service caused latency and stale stock reads.",
    "chosen_option": "Apache Kafka",
    "rationale": "Kafka gives durable ordered event streaming with consumer groups and replay for order events.",
    "options": ["Apache Kafka", "RabbitMQ", "Polling"],
    "tags": ["kafka", "messaging"],
}
OUTCOME = {
    "actual_results": "Order event latency dropped but consumer lag caused stuck orders during a network partition.",
    "regret_score": 4,
    "lessons": "Keep retry state outside process memory and alert on consumer lag.",
    "would_repeat": False,
    "metrics": {"p99_latency_ms": 120},
    "recorded_by": "sre-team",
}
PROPOSAL = (
    "RFC: use Kafka for streaming order events between order service and inventory service "
    "with consumer groups and replay to replace polling based integration."
)


async def _create(client, **over):
    r = await client.post("/api/decisions", json={**DECISION, **over})
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_decision_retains_and_flags_synced(client, memory):
    d = await _create(client)
    assert d["decision_id"].startswith("DEC-") and d["memory_synced"] is True
    assert d["decision_id"] in memory.records


async def test_before_after_outcome_changes_what_the_agent_can_say(client, memory, llm):
    """The demo story: same proposal, richer memory after an outcome is attached."""
    d = await _create(client)
    dec_id = d["decision_id"]
    llm.reply = f"## Briefing Summary\nSee [{dec_id}].\n"

    # BEFORE: decision known, no outcome
    before = (await client.post("/api/briefing", json={"proposal": PROPOSAL})).json()
    assert [x["decision_id"] for x in before["recalled_decisions"]] == [dec_id]
    assert before["recalled_decisions"][0]["has_outcome_memory"] is False
    assert "no outcome recorded" in llm.prompts[-1]
    assert "Regret score" not in llm.prompts[-1]

    r = await client.post(f"/api/decisions/{dec_id}/outcomes", json=OUTCOME)
    assert r.status_code == 201 and r.json()["memory_synced"] is True

    # AFTER: the outcome facts are now in the evidence the model sees
    after = (await client.post("/api/briefing", json={"proposal": PROPOSAL})).json()
    assert after["recalled_decisions"][0]["has_outcome_memory"] is True
    assert after["recalled_decisions"][0]["outcomes_on_record"] == 1
    assert "Regret score: 4/5" in llm.prompts[-1]
    assert "Keep retry state outside process memory" in llm.prompts[-1]
    assert "1 outcome(s) on record" in llm.prompts[-1]


async def test_no_memory_means_no_llm_call(client, llm):
    llm.reply = "SHOULD NEVER BE USED"
    r = await client.post("/api/briefing", json={"proposal": "x" * 60})
    body = r.json()
    assert r.status_code == 200
    assert llm.calls == 0
    assert body["model_used"].startswith("none")
    assert "No relevant institutional memory" in body["briefing"]
    assert body["cited_decisions"] == []


async def test_hallucinated_citation_is_flagged_and_audited(client, llm):
    d = await _create(client)
    dec_id = d["decision_id"]
    llm.reply = (
        f"### [{dec_id}]: Adopt Kafka\n- **Why this matters for the proposal:** Same tech.\n"
        "Also see [DEC-1999-042] which proves it works."
    )
    body = (await client.post("/api/briefing", json={"proposal": PROPOSAL})).json()

    assert body["unverified_citations"] == ["DEC-1999-042"]
    assert "DEC-1999-042 ⚠ UNVERIFIED" in body["briefing"]
    by_id = {c["decision_id"]: c for c in body["cited_decisions"]}
    assert by_id[dec_id]["verified"] is True and by_id[dec_id]["title"] == DECISION["title"]
    assert by_id[dec_id]["relevance_excerpt"] == "Same tech."
    assert by_id["DEC-1999-042"]["verified"] is False

    audit = (await client.get(f"/api/audit/{body['audit_id']}")).json()
    assert audit["recalled_decision_ids"] == [dec_id]
    assert audit["cited_decision_ids"] == [dec_id]
    assert audit["unverified_citation_ids"] == ["DEC-1999-042"]
    assert audit["recalled_memories"][0]["decision_id"] == dec_id


async def test_domain_filter_is_applied_to_recall(client, llm):
    await _create(client)
    llm.reply = "ok"
    hit = (await client.post("/api/briefing", json={"proposal": PROPOSAL, "domain": "platform"})).json()
    miss = (await client.post("/api/briefing", json={"proposal": PROPOSAL, "domain": "security"})).json()
    assert len(hit["recalled_decisions"]) == 1
    assert miss["recalled_decisions"] == [] and miss["model_used"].startswith("none")


async def test_hindsight_down_on_create_keeps_sql_row_and_resync_repairs(client, memory):
    memory.fail_retain = True
    r = await client.post("/api/decisions", json=DECISION)
    assert r.status_code == 503 and "/resync" in r.json()["detail"]

    listed = (await client.get("/api/decisions")).json()
    assert len(listed) == 1 and listed[0]["memory_synced"] is False
    dec_id = listed[0]["decision_id"]

    memory.fail_retain = False
    fixed = await client.post(f"/api/decisions/{dec_id}/resync")
    assert fixed.status_code == 200
    assert (await client.get(f"/api/decisions/{dec_id}")).json()["memory_synced"] is True
    assert dec_id in memory.records


async def test_recall_failure_is_503_not_a_guess(client, memory, llm):
    memory.fail_recall = True
    r = await client.post("/api/briefing", json={"proposal": PROPOSAL})
    assert r.status_code == 503 and llm.calls == 0


async def test_patch_status_re_retains(client, memory):
    d = await _create(client)
    r = await client.patch(f"/api/decisions/{d['decision_id']}", json={"status": "superseded"})
    assert r.status_code == 200
    assert "Status: superseded" in memory.records[d["decision_id"]]["text"]


async def test_outcome_on_unknown_decision_404(client):
    r = await client.post("/api/decisions/DEC-2000-001/outcomes", json=OUTCOME)
    assert r.status_code == 404


async def test_missing_outcomes_shrinks_after_outcome(client):
    d = await _create(client)
    assert [m["decision_id"] for m in (await client.get("/api/decisions/missing-outcomes")).json()] == [d["decision_id"]]
    await client.post(f"/api/decisions/{d['decision_id']}/outcomes", json=OUTCOME)
    assert (await client.get("/api/decisions/missing-outcomes")).json() == []


def test_strip_reasoning_removes_think_blocks():
    from app.llm import strip_reasoning
    assert strip_reasoning("<think>secret\nplan</think>\n## Briefing") == "## Briefing"
    assert strip_reasoning("<think>cut off by max_tokens") == ""
