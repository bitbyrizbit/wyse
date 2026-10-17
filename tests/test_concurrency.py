import threading

from helpers import belief, fact
from wyse.belief.ingest import remember
from wyse.belief.justify import claim_id_for
from wyse.belief.support import analyze, load_state

THREADS = 5
ITEMS = 6


def count(store, tenant, label):
    return store.read(tenant, f"MATCH (n:{label}) RETURN count(n) AS n")[0]["n"]


def test_concurrent_writers_leave_a_consistent_graph(store, ready):
    errors = []

    def writer(n):
        try:
            for i in range(ITEMS):
                fact(store, ready, "tool", f"src{n}", f"seen item {i}", f"item-{i}", "status", "ok")
                fact(store, ready, "tool", f"src{n}", f"own note {i}", f"own-{n}-{i}", "status", "ok")
            if n == 0:
                fact(store, ready, "web", "blog", "item zero is bad", "item-0", "status", "bad")
        except Exception as exc:
            errors.append(repr(exc))

    pool = [threading.Thread(target=writer, args=(n,)) for n in range(THREADS)]
    for thread in pool:
        thread.start()
    for thread in pool:
        thread.join()

    assert errors == []
    assert count(store, ready, "Claim") == ITEMS + THREADS * ITEMS + 1
    assert count(store, ready, "Justification") == 2 * THREADS * ITEMS + 1
    assert count(store, ready, "Observation") == 2 * THREADS * ITEMS + 1

    state = load_state(store, ready)
    analysis = analyze(state)
    assert state.claims == analysis.belief
    assert state.justification_state == analysis.justification_state

    assert belief(store, ready, claim_id_for("item-0", "status", "ok")) == "SUPPORTED"
    assert belief(store, ready, claim_id_for("item-0", "status", "bad")) == "CONTESTED"


def test_repeating_an_operation_id_adds_nothing(store, ready):
    for _ in range(2):
        remember(
            store, ready, source_kind="tool", source_name="ledger", content="paid",
            subject="inv-1", predicate="status", object="paid", operation_id="op-1",
        )
    assert count(store, ready, "Observation") == 1
    assert count(store, ready, "Justification") == 1
