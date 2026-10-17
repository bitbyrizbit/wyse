import pytest

from helpers import fact
from wyse.agents.scopes import scratch_scope


def test_scratch_memory_is_invisible_to_shared_and_to_other_agents(store, ready, scratch):
    mine = scratch("alice")
    theirs = scratch("bob")
    fact(store, mine, "tool", "ledger", "paid", "inv-1", "status", "paid")
    assert store.read(ready, "MATCH (c:Claim) RETURN count(c) AS n")[0]["n"] == 0
    assert store.read(theirs, "MATCH (c:Claim) RETURN count(c) AS n")[0]["n"] == 0
    assert store.read(mine, "MATCH (c:Claim) RETURN count(c) AS n")[0]["n"] == 1


def test_scope_ids_reject_unsafe_names():
    for bad in ("", "Alice", "a-b", "x" * 17):
        with pytest.raises(ValueError):
            scratch_scope("acme", bad)
    with pytest.raises(ValueError):
        scratch_scope("acme_a_x", "bob")
