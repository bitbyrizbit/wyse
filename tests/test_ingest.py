import inspect

import pytest

from wyse.belief.ingest import assert_claim, record_observation, remember
from wyse.belief.justify import claim_id_for
from wyse.belief.policy import tier_for_kind
from wyse.belief.support import analyze, load_state, recompute
from wyse.models import TrustTier
from wyse.schema import ensure_schema, wait_for_constraints


@pytest.fixture
def ready(store, tenant):
    store.write(tenant, "CREATE (:Seed)")
    ensure_schema(store, tenant)
    wait_for_constraints(store, tenant)
    return tenant


def fact(store, tenant, kind, name, content, subject, predicate, obj):
    return remember(
        store, tenant, source_kind=kind, source_name=name, content=content,
        subject=subject, predicate=predicate, object=obj,
    )


def belief(store, tenant, claim_id):
    rows = store.read(tenant, "MATCH (c:Claim {id: $id}) RETURN c.belief_status AS s", {"id": claim_id})
    return rows[0]["s"]


def quarantine(store, tenant, source_id):
    store.write(tenant, "MATCH (s:Source {id: $id}) SET s.incident_state = 'QUARANTINED'", {"id": source_id})
    recompute(store, tenant)


def test_alternative_support_survives_one_source_failing(store, ready):
    a = fact(store, ready, "tool", "provider", "settled", "inv-104", "status", "settled")
    b = fact(store, ready, "system", "bank", "settled too", "inv-104", "status", "settled")
    assert a.claim_id == b.claim_id
    quarantine(store, ready, a.source_id)
    assert belief(store, ready, a.claim_id) == "SUPPORTED"
    quarantine(store, ready, b.source_id)
    assert belief(store, ready, a.claim_id) == "UNSUPPORTED"


def test_joint_premises_are_all_required(store, ready):
    settled = fact(store, ready, "tool", "ledger", "settled", "inv-104", "status", "settled")
    clear = fact(store, ready, "tool", "crm", "no other open invoices", "cust-9", "open invoices", "none")
    derived = assert_claim(
        store, ready, subject="cust-9", predicate="balance", object="zero",
        evidence=[[settled.claim_id, clear.claim_id]], rule="all clear",
    )
    assert belief(store, ready, derived) == "SUPPORTED"
    quarantine(store, ready, clear.source_id)
    assert belief(store, ready, derived) == "UNSUPPORTED"
    assert belief(store, ready, settled.claim_id) == "SUPPORTED"


def test_higher_trust_wins_a_contradiction(store, ready):
    web = fact(store, ready, "web", "blog", "paid", "inv-7", "status", "paid")
    ledger = fact(store, ready, "system", "ledger", "unpaid", "inv-7", "status", "unpaid")
    assert belief(store, ready, web.claim_id) == "CONTESTED"
    assert belief(store, ready, ledger.claim_id) == "SUPPORTED"
    links = store.read(ready, "MATCH (:Claim)-[r:CONTRADICTS]->(:Claim) RETURN count(r) AS n")
    assert links[0]["n"] == 1


def test_equal_standing_contests_both_claims(store, ready):
    a = fact(store, ready, "tool", "t1", "paid", "inv-8", "status", "paid")
    b = fact(store, ready, "tool", "t2", "unpaid", "inv-8", "status", "unpaid")
    assert belief(store, ready, a.claim_id) == "CONTESTED"
    assert belief(store, ready, b.claim_id) == "CONTESTED"


def test_more_independent_sources_break_a_tie(store, ready):
    x = fact(store, ready, "tool", "t1", "c1", "s", "k", "a")
    fact(store, ready, "tool", "t2", "c2", "s", "k", "a")
    y = fact(store, ready, "tool", "t3", "c3", "s", "k", "b")
    assert belief(store, ready, x.claim_id) == "SUPPORTED"
    assert belief(store, ready, y.claim_id) == "CONTESTED"


def test_three_agents_citing_one_origin_is_one_root(store, ready):
    origin = record_observation(
        store, ready, source_kind="web", source_name="mailbox", content="bank details changed",
    )
    checks = [
        assert_claim(
            store, ready, subject=f"agent{i}", predicate="verified", object="bank change",
            evidence=[[origin.observation_id]], agent_id=f"agent{i}",
        )
        for i in range(3)
    ]
    final = assert_claim(
        store, ready, subject="supplier-1", predicate="bank", object="changed",
        evidence=[[check] for check in checks],
    )
    analysis = analyze(load_state(store, ready))
    assert analysis.belief[final] == "SUPPORTED"
    assert analysis.roots[final] == {origin.observation_id}
    assert len(analysis.independent_sources[final]) == 1


def test_dangling_premise_is_rejected_before_any_write(store, ready):
    with pytest.raises(ValueError):
        assert_claim(
            store, ready, subject="a", predicate="b", object="c",
            evidence=[["obs_0123456789abcdef"]],
        )
    assert store.read(ready, "MATCH (c:Claim) RETURN count(c) AS n")[0]["n"] == 0


def test_a_claim_cannot_justify_itself(store, ready):
    own = claim_id_for("a", "b", "c")
    with pytest.raises(ValueError):
        assert_claim(store, ready, subject="a", predicate="b", object="c", evidence=[[own]])


def test_malformed_premise_ids_are_rejected(store, ready):
    with pytest.raises(ValueError):
        assert_claim(store, ready, subject="a", predicate="b", object="c", evidence=[["foo_1"]])


def test_repeating_the_same_evidence_adds_nothing(store, ready):
    first = fact(store, ready, "tool", "ledger", "paid", "inv-1", "status", "paid")
    assert_claim(
        store, ready, subject="inv-1", predicate="status", object="paid",
        evidence=[[first.observation_id]],
    )
    assert store.read(ready, "MATCH (j:Justification) RETURN count(j) AS n")[0]["n"] == 1
    assert store.read(ready, "MATCH (c:Claim) RETURN count(c) AS n")[0]["n"] == 1


def test_trust_tier_is_assigned_by_the_server(store, ready):
    params = inspect.signature(remember).parameters
    assert "trust_tier" not in params
    assert "tier" not in params
    assert tier_for_kind("banana") == TrustTier.WEB
    fact(store, ready, "banana", "mystery", "hello", "x", "y", "z")
    row = store.read(ready, "MATCH (s:Source) RETURN s.trust_tier AS t")[0]
    assert row["t"] == "WEB"
