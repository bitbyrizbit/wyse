from bench.baselines import Cascade, Plain
from bench.metrics import score
from bench.oracle import expected_flags, supported_claims
from bench.scenarios import Decision, Proof, Scenario, generate
from bench.wyse_system import Wyse


def hand():
    return Scenario(
        seed=0,
        sources={"s1": "tool", "s2": "web", "s3": "agent"},
        mirrors={},
        claims={
            "c0": [Proof(source="s1"), Proof(source="s2")],
            "c1": [Proof(source="s3")],
            "c2": [Proof(parents=("c0", "c1"))],
            "c3": [Proof(source="s1")],
            "c4": [Proof(parents=("c3", "c1"))],
        },
        decisions=[
            Decision("d0", ("c0",), False),
            Decision("d1", ("c2",), False),
            Decision("d2", ("c3",), True),
            Decision("d3", ("c1",), False),
        ],
        reported=["s1"],
    )


def test_generator_is_deterministic_and_topological():
    first, second = generate(3), generate(3)
    assert first.claims == second.claims
    assert first.reported == second.reported
    seen: set[str] = set()
    for cid, proofs in first.claims.items():
        for proof in proofs:
            assert all(parent in seen for parent in proof.parents)
        seen.add(cid)


def test_oracle_separates_falling_from_surviving_claims():
    scenario = hand()
    alive = supported_claims(scenario, scenario.truth_bad)
    assert set(scenario.claims) - alive == {"c3", "c4"}
    assert expected_flags(scenario) == {"d0": "REVIEW", "d1": "REVIEW", "d2": "CORRECTION"}


def test_baselines_fail_in_their_characteristic_ways():
    scenario = hand()
    plain, cascade = Plain(), Cascade()
    plain.load(scenario)
    cascade.load(scenario)
    p = score(scenario, plain.compromise(scenario.reported))
    c = score(scenario, cascade.compromise(scenario.reported))
    assert p["leakage"] == 0.5
    assert p["preserved"] == 1.0
    assert p["missed"] == 1.0
    assert c["leakage"] == 0.0
    assert abs(c["preserved"] - 1 / 3) < 1e-9
    assert c["precision"] == 0.5
    assert abs(c["labelled"] - 1 / 3) < 1e-9


def mirror_case():
    return Scenario(
        seed=0,
        sources={"s1": "tool", "m_s1": "tool"},
        mirrors={"s1": "m_s1"},
        claims={"c0": [Proof(source="s1"), Proof(source="m_s1")]},
        decisions=[Decision("d0", ("c0",), True)],
        reported=["s1"],
    )


def run_wyse(store, scenario):
    system = Wyse(store)
    system.load(scenario)
    try:
        return score(scenario, system.compromise(scenario.reported))
    finally:
        system.close()


def test_hidden_mirror_defeats_independence_but_not_cascade(store):
    scenario = mirror_case()
    cascade = Cascade()
    cascade.load(scenario)
    c = score(scenario, cascade.compromise(scenario.reported))
    w = run_wyse(store, scenario)
    assert w["leakage"] == 1.0
    assert w["labelled"] == 0.0
    assert c["leakage"] == 0.0
    assert c["labelled"] == 1.0


def test_wyse_matches_the_oracle_on_clean_scenarios(store):
    for seed in range(3):
        row = run_wyse(store, generate(seed, n_base=12, n_derived=8, n_decisions=6))
        assert row["leakage"] in (0.0, None)
        assert row["preserved"] in (1.0, None)
        assert row["precision"] == 1.0
        assert row["missed"] in (0.0, None)
        assert row["labelled"] in (1.0, None)
