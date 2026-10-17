import pytest

from helpers import belief, fact
from wyse.belief.ingest import assert_claim
from wyse.governance.asof import reassess, recorded_context
from wyse.governance.audit import explain_belief, list_incidents, observation_nodes
from wyse.governance.decisions import UnusableClaims, record_decision
from wyse.governance.gateway import recall
from wyse.governance.impact import inspect_impact
from wyse.governance.quarantine import quarantine_source
from wyse.governance.retract import retract_claim
from wyse.models import Remediation


def test_gateway_withholds_without_waiting_for_recompute(store, ready):
    page = fact(store, ready, "web", "blog", "paid", "inv-1", "status", "paid")
    store.write(
        ready, "MATCH (s:Source {id: $id}) SET s.incident_state = 'QUARANTINED'", {"id": page.source_id}
    )
    result = recall(store, ready, subject="inv-1")
    assert result.usable == []
    assert result.contested == []
    assert result.withheld[0]["claim_id"] == page.claim_id
    assert "statement" not in result.withheld[0]
    assert belief(store, ready, page.claim_id) == "SUPPORTED"


def test_quarantine_keeps_independently_supported_claims(store, ready):
    web = fact(store, ready, "web", "blog", "paid", "inv-104", "status", "paid")
    fact(store, ready, "tool", "provider", "paid", "inv-104", "status", "paid")
    _, impact = quarantine_source(store, ready, web.source_id, "page was forged")
    assert impact.fell == []
    assert impact.survived == [web.claim_id]
    assert [i["claim_id"] for i in recall(store, ready, subject="inv-104").usable] == [web.claim_id]


def test_fallen_claim_flags_the_decision_that_acted_on_it(store, ready):
    web = fact(store, ready, "web", "blog", "paid", "inv-104", "status", "paid")
    decision = record_decision(
        store, ready, agent_id="billing", summary="closed the invoice",
        claim_ids=[web.claim_id], acted=True,
    )
    _, impact = quarantine_source(store, ready, web.source_id, "page was forged")
    assert impact.fell == [web.claim_id]
    assert impact.decisions == {decision: Remediation.COMPENSATING_ACTION_REQUIRED}
    row = store.read(ready, "MATCH (d:Decision {id: $id}) RETURN d.remediation AS r", {"id": decision})[0]
    assert row["r"] == "COMPENSATING_ACTION_REQUIRED"


def test_surviving_claim_still_flags_a_decision_built_on_bad_evidence(store, ready):
    web = fact(store, ready, "web", "blog", "paid", "inv-104", "status", "paid")
    fact(store, ready, "tool", "provider", "paid", "inv-104", "status", "paid")
    decision = record_decision(
        store, ready, agent_id="billing", summary="closed the invoice", claim_ids=[web.claim_id],
    )
    _, impact = quarantine_source(store, ready, web.source_id, "page was forged")
    assert impact.fell == []
    assert impact.decisions == {decision: Remediation.REVIEW_REQUIRED}
    assert belief(store, ready, web.claim_id) == "SUPPORTED"


def test_preview_matches_the_real_run(store, ready):
    web = fact(store, ready, "web", "blog", "paid", "inv-104", "status", "paid")
    fact(store, ready, "tool", "provider", "paid", "inv-104", "status", "paid")
    solo = fact(store, ready, "web", "blog", "paid too", "inv-9", "status", "paid")
    record_decision(store, ready, agent_id="billing", summary="closed inv-9", claim_ids=[solo.claim_id])
    preview = inspect_impact(store, ready, source_id=web.source_id)
    _, actual = quarantine_source(store, ready, web.source_id, "page was forged")
    assert (preview.fell, preview.survived, preview.decisions) == (
        actual.fell, actual.survived, actual.decisions,
    )
    assert actual.fell == [solo.claim_id]


def test_retraction_cascades_through_derived_claims(store, ready):
    base = fact(store, ready, "tool", "ledger", "settled", "inv-1", "status", "settled")
    derived = assert_claim(
        store, ready, subject="cust-1", predicate="balance", object="zero",
        evidence=[[base.claim_id]],
    )
    assert belief(store, ready, derived) == "SUPPORTED"
    _, impact = retract_claim(store, ready, base.claim_id, "ledger entry was reversed")
    assert belief(store, ready, base.claim_id) == "RETRACTED"
    assert belief(store, ready, derived) == "UNSUPPORTED"
    assert sorted(impact.fell) == sorted([base.claim_id, derived])


def test_decisions_cannot_use_withheld_claims(store, ready):
    web = fact(store, ready, "web", "blog", "paid", "inv-1", "status", "paid")
    quarantine_source(store, ready, web.source_id, "page was forged")
    with pytest.raises(UnusableClaims) as caught:
        record_decision(store, ready, agent_id="billing", summary="close it", claim_ids=[web.claim_id])
    assert caught.value.problems == {web.claim_id: "UNSUPPORTED"}


def test_recorded_context_is_frozen_while_reassessment_moves_on(store, ready):
    claim = fact(store, ready, "tool", "ledger", "settled", "inv-1", "status", "settled")
    decision = record_decision(
        store, ready, agent_id="billing", summary="closed the invoice", claim_ids=[claim.claim_id],
    )
    retract_claim(store, ready, claim.claim_id, "ledger entry was reversed")
    frozen = recorded_context(store, ready, decision)
    assert frozen["claims"][0]["belief"] == "SUPPORTED"
    verdict = reassess(store, ready, decision)
    assert verdict["remediation"] == "CORRECTION_REQUIRED"
    assert verdict["fallen"] == [claim.claim_id]


def test_claim_quarantine_blocks_dependents_without_other_paths(store, ready):
    a = fact(store, ready, "tool", "t1", "a", "x", "k", "a")
    b = fact(store, ready, "tool", "t2", "b", "y", "k", "b")
    only_a = assert_claim(
        store, ready, subject="d1", predicate="p", object="o", evidence=[[a.claim_id]],
    )
    either = assert_claim(
        store, ready, subject="d2", predicate="p", object="o", evidence=[[a.claim_id], [b.claim_id]],
    )
    store.write(
        ready, "MATCH (c:Claim {id: $id}) SET c.use_status = 'QUARANTINED'", {"id": a.claim_id}
    )
    result = recall(store, ready)
    usable = {item["claim_id"] for item in result.usable}
    withheld = {item["claim_id"]: item["reason"] for item in result.withheld}
    assert withheld[a.claim_id] == "QUARANTINED"
    assert withheld[only_a] == "BLOCKED_BY_QUARANTINE"
    assert either in usable
    assert b.claim_id in usable


def test_explanation_shows_the_proof_and_hides_poisoned_text(store, ready):
    web = fact(store, ready, "web", "blog", "forged ledger page", "inv-104", "status", "paid")
    tool = fact(store, ready, "tool", "provider", "provider says paid", "inv-104", "status", "paid")
    quarantine_source(store, ready, web.source_id, "page was forged")
    report = explain_belief(store, ready, web.claim_id)
    assert report["belief"] == "SUPPORTED"
    nodes = {node["id"]: node for node in observation_nodes(report["tree"])}
    assert nodes[web.observation_id]["valid"] is False
    assert "content" not in nodes[web.observation_id]
    assert nodes[tool.observation_id]["content"] == "provider says paid"


def test_incidents_are_logged_with_their_results(store, ready):
    web = fact(store, ready, "web", "blog", "paid", "inv-1", "status", "paid")
    quarantine_source(store, ready, web.source_id, "page was forged")
    log = list_incidents(store, ready)
    assert len(log) == 1
    assert log[0]["kind"] == "QUARANTINE"
    assert log[0]["result"]["fell"] == [web.claim_id]


def test_unknown_targets_are_rejected_and_change_nothing(store, ready):
    web = fact(store, ready, "web", "blog", "paid", "inv-1", "status", "paid")
    with pytest.raises(ValueError):
        quarantine_source(store, ready, "src_0000000000000000", "no such source")
    assert belief(store, ready, web.claim_id) == "SUPPORTED"
    assert list_incidents(store, ready) == []
