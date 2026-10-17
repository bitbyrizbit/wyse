import json

from wyse.belief.policy import MAX_FIELD, check_text
from wyse.belief.support import analyze, load_state
from wyse.db import Store
from wyse.ids import new_id, now_ms

DECISION = """
MERGE (a:Agent {id: $aid})
  ON CREATE SET a.tenant = $tenant, a.role = 'agent', a.scope = 'private'
CREATE (d:Decision {id: $did, tenant: $tenant, summary: $summary, decided_at: $now,
                    policy_version: $policy, remediation: 'NO_ACTION_REQUIRED',
                    acted: $acted, snapshot: $snapshot})
CREATE (a)-[:MADE]->(d)
WITH d
UNWIND $claims AS cid
MATCH (c:Claim {id: cid})
CREATE (d)-[:USED]->(c)
RETURN count(c) AS used
"""


class UnusableClaims(ValueError):
    def __init__(self, problems: dict[str, str]):
        super().__init__(f"claims cannot be used: {problems}")
        self.problems = problems


def record_decision(
    store: Store, tenant: str, *, agent_id: str, summary: str, claim_ids: list[str],
    acted: bool = False, policy_version: str = "policy-1", allow_contested: bool = False,
) -> str:
    who = check_text("agent_id", agent_id, MAX_FIELD)
    what = check_text("summary", summary, MAX_FIELD)
    ids = sorted(set(claim_ids))
    if not ids:
        raise ValueError("a decision must cite at least one claim")

    state = load_state(store, tenant)
    analysis = analyze(state)
    problems: dict[str, str] = {}
    for cid in ids:
        if cid not in state.claims:
            problems[cid] = "UNKNOWN"
        elif cid in analysis.usable:
            continue
        elif allow_contested and analysis.belief[cid] == "CONTESTED" and cid in analysis.use_ok:
            continue
        else:
            problems[cid] = analysis.belief[cid] if analysis.belief[cid] != "SUPPORTED" else "BLOCKED"
    if problems:
        raise UnusableClaims(problems)

    now = now_ms()
    snapshot = {
        "policy": policy_version,
        "decided_at": now,
        "claims": {
            cid: {
                "revision": state.claim_meta[cid]["revision"],
                "belief": analysis.belief[cid],
                "evidence": sorted(analysis.roots.get(cid, ())),
            }
            for cid in ids
        },
    }
    decision_id = new_id("dec")
    rows = store.write(
        tenant,
        DECISION,
        {
            "aid": who, "did": decision_id, "tenant": tenant, "summary": what, "now": now,
            "policy": policy_version, "acted": acted,
            "snapshot": json.dumps(snapshot, sort_keys=True), "claims": ids,
        },
    )
    if rows[0]["used"] != len(ids):
        raise RuntimeError("decision was written with missing claims")
    return decision_id
