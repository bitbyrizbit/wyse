from wyse.belief.policy import MAX_FIELD, check_text
from wyse.db import Store
from wyse.governance.impact import Impact, run_with_impact
from wyse.ids import new_id, now_ms

QUARANTINE = """
MATCH (s:Source {id: $sid})
SET s.incident_state = 'QUARANTINED'
CREATE (i:Incident {id: $iid, tenant: $tenant, kind: 'QUARANTINE', reason: $reason,
                    created_at: $now, result: '', target: $sid})
RETURN i.id AS id
"""


def quarantine_source(store: Store, tenant: str, source_id: str, reason: str) -> tuple[str, Impact]:
    why = check_text("reason", reason, MAX_FIELD)

    def write() -> str:
        rows = store.write(
            tenant, QUARANTINE,
            {"sid": source_id, "iid": new_id("inc"), "tenant": tenant, "reason": why, "now": now_ms()},
        )
        if not rows:
            raise ValueError(f"unknown source: {source_id}")
        return rows[0]["id"]

    return run_with_impact(store, tenant, write)
