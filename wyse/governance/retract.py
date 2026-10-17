from wyse.belief.policy import MAX_FIELD, check_text
from wyse.db import Store
from wyse.governance.impact import Impact, run_with_impact
from wyse.ids import new_id, now_ms

RETRACT_CLAIM = """
MATCH (c:Claim {id: $id})
WHERE c.belief_status <> 'RETRACTED'
SET c.belief_status = 'RETRACTED', c.revision = c.revision + 1
CREATE (i:Incident {id: $iid, tenant: $tenant, kind: 'RETRACTION', reason: $reason,
                    created_at: $now, result: '', target: $id})
CREATE (i)-[:INVALIDATED]->(c)
RETURN i.id AS id
"""

RETRACT_OBSERVATION = """
MATCH (o:Observation {id: $id})
CREATE (i:Incident {id: $iid, tenant: $tenant, kind: 'RETRACTION', reason: $reason,
                    created_at: $now, result: '', target: $id})
CREATE (i)-[:INVALIDATED]->(o)
RETURN i.id AS id
"""


def _retract(store: Store, tenant: str, query: str, target: str, reason: str, label: str):
    why = check_text("reason", reason, MAX_FIELD)

    def write() -> str:
        rows = store.write(
            tenant, query,
            {"id": target, "iid": new_id("inc"), "tenant": tenant, "reason": why, "now": now_ms()},
        )
        if not rows:
            raise ValueError(f"{label}: {target}")
        return rows[0]["id"]

    return run_with_impact(store, tenant, write)


def retract_claim(store: Store, tenant: str, claim_id: str, reason: str) -> tuple[str, Impact]:
    return _retract(store, tenant, RETRACT_CLAIM, claim_id, reason, "unknown or already retracted claim")


def retract_observation(store: Store, tenant: str, observation_id: str, reason: str) -> tuple[str, Impact]:
    return _retract(store, tenant, RETRACT_OBSERVATION, observation_id, reason, "unknown observation")
