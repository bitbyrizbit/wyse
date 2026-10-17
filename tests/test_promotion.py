from helpers import belief, fact
from wyse.agents.promotion import promote, revoke_promotion
from wyse.belief.support import analyze, load_state
from wyse.governance.audit import explain_belief, observation_nodes
from wyse.governance.quarantine import quarantine_source


def test_only_usable_claims_are_promoted(store, ready, scratch):
    scope = scratch("alice")
    good = fact(store, scope, "tool", "ledger", "paid", "inv-1", "status", "paid")
    bad = fact(store, scope, "web", "blog", "unpaid", "inv-2", "status", "unpaid")
    quarantine_source(store, scope, bad.source_id, "forged")
    outcome = promote(store, ready, "alice", [good.claim_id, bad.claim_id])
    assert outcome.promoted == [good.claim_id]
    assert outcome.held == {bad.claim_id: "UNSUPPORTED"}
    assert belief(store, ready, good.claim_id) == "SUPPORTED"
    assert store.read(ready, "MATCH (c:Claim {id: $id}) RETURN count(c) AS n", {"id": bad.claim_id})[0]["n"] == 0


def test_promotion_carries_provenance(store, ready, scratch):
    scope = scratch("alice")
    seen = fact(store, scope, "tool", "ledger", "ledger says paid", "inv-1", "status", "paid")
    promote(store, ready, "alice", [seen.claim_id])
    nodes = list(observation_nodes(explain_belief(store, ready, seen.claim_id)["tree"]))
    assert [node["id"] for node in nodes] == [seen.observation_id]
    assert nodes[0]["content"] == "ledger says paid"
    assert nodes[0]["source_name"] == "ledger"


def test_independence_is_counted_across_scopes(store, ready, scratch):
    first = fact(store, scratch("alice"), "tool", "ledger", "paid", "inv-1", "status", "paid")
    second = fact(store, scratch("bob"), "tool", "ledger", "paid", "inv-1", "status", "paid")
    promote(store, ready, "alice", [first.claim_id])
    promote(store, ready, "bob", [second.claim_id])
    analysis = analyze(load_state(store, ready))
    assert len(analysis.independent_sources[first.claim_id]) == 1
    third = fact(store, scratch("carol"), "tool", "bank", "paid", "inv-1", "status", "paid")
    promote(store, ready, "carol", [third.claim_id])
    analysis = analyze(load_state(store, ready))
    assert len(analysis.independent_sources[first.claim_id]) == 2


def test_promotion_caps_the_trust_tier(store, ready, scratch):
    seen = fact(store, scratch("alice"), "system", "ledger", "paid", "inv-1", "status", "paid")
    promote(store, ready, "alice", [seen.claim_id])
    assert store.read(ready, "MATCH (s:Source) RETURN s.trust_tier AS t")[0]["t"] == "TOOL"


def test_equal_standing_conflicts_are_held_and_stronger_ones_win(store, ready, scratch):
    fact(store, ready, "tool", "t1", "paid", "inv-1", "status", "paid")
    equal = fact(store, scratch("alice"), "tool", "t2", "unpaid", "inv-1", "status", "unpaid")
    held = promote(store, ready, "alice", [equal.claim_id])
    assert held.held == {equal.claim_id: "CONFLICT"}

    bob = scratch("bob")
    fact(store, bob, "tool", "t3", "unpaid", "inv-1", "status", "unpaid")
    strong = fact(store, bob, "tool", "t4", "unpaid too", "inv-1", "status", "unpaid")
    won = promote(store, ready, "bob", [strong.claim_id])
    assert won.promoted == [strong.claim_id]
    assert won.shared[strong.claim_id] == "SUPPORTED"


def test_promotions_are_recorded_and_reversible(store, ready, scratch):
    seen = fact(store, scratch("alice"), "tool", "ledger", "paid", "inv-1", "status", "paid")
    outcome = promote(store, ready, "alice", [seen.claim_id])
    linked = store.read(
        ready, "MATCH (:Promotion {id: $id})-[:PROMOTED]->(c:Claim) RETURN c.id AS id",
        {"id": outcome.promotion_id},
    )
    assert [row["id"] for row in linked] == [seen.claim_id]
    revoke_promotion(store, ready, outcome.promotion_id, "alice was wrong")
    assert belief(store, ready, seen.claim_id) == "RETRACTED"


def test_promoting_twice_adds_nothing(store, ready, scratch):
    seen = fact(store, scratch("alice"), "tool", "ledger", "paid", "inv-1", "status", "paid")
    promote(store, ready, "alice", [seen.claim_id])
    promote(store, ready, "alice", [seen.claim_id])
    for label in ("Claim", "Justification", "Observation"):
        rows = store.read(ready, f"MATCH (n:{label}) RETURN count(n) AS n")
        assert rows[0]["n"] == 1
