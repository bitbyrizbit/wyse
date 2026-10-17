import pytest

from helpers import fact
from wyse.agents.handoff import handoff, open_handoff
from wyse.governance.quarantine import quarantine_source
from wyse.governance.retract import retract_claim


def test_handoff_carries_provenance_and_hides_withheld_text(store, ready):
    good = fact(store, ready, "tool", "ledger", "paid", "inv-1", "status", "paid")
    bad = fact(store, ready, "web", "blog", "unpaid", "inv-2", "status", "unpaid")
    quarantine_source(store, ready, bad.source_id, "forged")
    sent = handoff(store, ready, "alice", "bob", [good.claim_id, bad.claim_id], note="finish the invoice")
    opened = open_handoff(store, ready, sent, "bob")
    assert [item["claim_id"] for item in opened["claims"]] == [good.claim_id]
    assert opened["claims"][0]["evidence"] == [good.observation_id]
    assert opened["withheld"][0]["claim_id"] == bad.claim_id
    assert "statement" not in opened["withheld"][0]
    assert opened["drift"] == []


def test_handoff_detects_drift_and_wrong_recipients(store, ready):
    good = fact(store, ready, "tool", "ledger", "paid", "inv-1", "status", "paid")
    sent = handoff(store, ready, "alice", "bob", [good.claim_id])
    with pytest.raises(PermissionError):
        open_handoff(store, ready, sent, "carol")
    retract_claim(store, ready, good.claim_id, "ledger reversed")
    drift = open_handoff(store, ready, sent, "bob")["drift"]
    assert drift[0]["claim_id"] == good.claim_id
    assert drift[0]["now"]["belief"] == "RETRACTED"
