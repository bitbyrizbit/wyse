from wyse.belief.support import analyze, load_state
from wyse.db import Store
from wyse.governance.impact import apply_remediation
from wyse.governance.remediation import classify


def _decision(state, decision_id: str) -> dict:
    found = state.decisions.get(decision_id)
    if found is None:
        raise ValueError(f"unknown decision: {decision_id}")
    return found


def recorded_context(store: Store, tenant: str, decision_id: str) -> dict:
    state = load_state(store, tenant)
    decision = _decision(state, decision_id)
    snapshot = decision["snapshot"]
    if snapshot is None:
        raise ValueError("decision has no recorded snapshot")
    claims = []
    for cid, entry in sorted(snapshot["claims"].items()):
        meta = state.claim_meta[cid]
        claims.append(
            {
                "claim_id": cid,
                "statement": {
                    "subject": meta["subject"], "predicate": meta["predicate"], "object": meta["object"],
                },
                "revision": entry["revision"],
                "belief": entry["belief"],
                "evidence": entry["evidence"],
            }
        )
    return {
        "decision_id": decision_id,
        "summary": decision["summary"],
        "decided_at": decision["decided_at"],
        "policy": snapshot["policy"],
        "acted": decision["acted"],
        "claims": claims,
    }


def reassess(store: Store, tenant: str, decision_id: str, persist: bool = False) -> dict:
    state = load_state(store, tenant)
    analysis = analyze(state)
    decision = _decision(state, decision_id)
    used = set(decision["claims"])
    fallen = used - analysis.use_ok
    contested = {cid for cid in used if analysis.belief[cid] == "CONTESTED"}
    snapshot = decision["snapshot"]
    recorded = {r for e in snapshot["claims"].values() for r in e["evidence"]} if snapshot else set()
    dead = recorded - analysis.grounded
    verdict = classify(decision, fallen, contested, dead)
    if persist:
        apply_remediation(store, tenant, {decision_id: verdict})
    return {
        "decision_id": decision_id,
        "remediation": str(verdict),
        "fallen": sorted(fallen),
        "contested": sorted(contested),
        "dead_evidence": sorted(dead),
    }
