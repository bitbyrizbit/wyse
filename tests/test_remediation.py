from wyse.governance.remediation import classify
from wyse.models import Remediation


def decision(claims=("c1",), acted=False, evidence=("o1",), snapshot=True):
    snap = {"claims": {c: {"revision": 1, "belief": "SUPPORTED", "evidence": list(evidence)} for c in claims}}
    return {"claims": list(claims), "acted": acted, "snapshot": snap if snapshot else None}


def test_fallen_claim_demands_correction():
    assert classify(decision(), {"c1"}, set(), set()) == Remediation.CORRECTION_REQUIRED


def test_fallen_claim_after_action_demands_compensation():
    result = classify(decision(acted=True), {"c1"}, set(), set())
    assert result == Remediation.COMPENSATING_ACTION_REQUIRED


def test_survivor_with_dead_evidence_needs_review():
    assert classify(decision(), set(), set(), {"o1"}) == Remediation.REVIEW_REQUIRED


def test_touched_survivor_needs_review():
    assert classify(decision(), set(), {"c1"}, set()) == Remediation.REVIEW_REQUIRED


def test_unaffected_decision_needs_nothing():
    assert classify(decision(), {"other"}, {"other"}, {"o9"}) == Remediation.NO_ACTION_REQUIRED


def test_missing_snapshot_with_touch_is_unresolved():
    result = classify(decision(snapshot=False), set(), {"c1"}, set())
    assert result == Remediation.UNRESOLVED


def test_missing_snapshot_without_touch_is_quiet():
    assert classify(decision(snapshot=False), set(), set(), set()) == Remediation.NO_ACTION_REQUIRED
