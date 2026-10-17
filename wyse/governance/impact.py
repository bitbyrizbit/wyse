import json
from dataclasses import dataclass, replace

from wyse.belief.support import State, analyze, load_state, recompute
from wyse.db import Store
from wyse.governance.remediation import classify
from wyse.models import Remediation

LIVE = ("SUPPORTED", "CONTESTED")
DEAD = ("UNSUPPORTED", "RETRACTED")


@dataclass
class Impact:
    fell: list[str]
    survived: list[str]
    changed: list[dict]
    decisions: dict[str, Remediation]

    def as_dict(self) -> dict:
        return {
            "fell": self.fell,
            "survived": self.survived,
            "changed": self.changed,
            "decisions": {key: str(value) for key, value in self.decisions.items()},
        }


def hypothetical(state: State, *, sources=(), observations=(), claims=()) -> State:
    dead = set(sources)
    observed = {
        oid: ({**row, "state": "QUARANTINED"} if row["source"] in dead else row)
        for oid, row in state.observations.items()
    }
    return replace(
        state,
        observations=observed,
        invalidated=state.invalidated | set(observations) | set(claims),
    )


def compare(state: State, before, after) -> Impact:
    live = {cid for cid, status in before.belief.items() if status in LIVE}
    fell = sorted(cid for cid in live if after.belief[cid] in DEAD)

    flipped = {
        jid for jid, value in before.justification_state.items()
        if value == "VALID" and after.justification_state.get(jid) == "INVALID"
    }
    touched = {j.claim for j in state.justifications if j.id in flipped}
    touched |= {
        cid for cid in live
        if before.belief[cid] == "SUPPORTED" and after.belief[cid] == "CONTESTED"
    }
    survived = sorted(cid for cid in touched if after.belief[cid] in LIVE)

    changed = [
        {"claim": cid, "before": before.belief[cid], "after": after.belief[cid]}
        for cid in sorted(before.belief)
        if before.belief[cid] != after.belief[cid]
    ]

    dead_evidence = before.grounded - after.grounded
    decisions: dict[str, Remediation] = {}
    for did, decision in state.decisions.items():
        label = classify(decision, set(fell), touched, dead_evidence)
        if label != Remediation.NO_ACTION_REQUIRED:
            decisions[did] = label
    return Impact(fell, survived, changed, decisions)


def inspect_impact(
    store: Store, tenant: str, *, source_id: str | None = None,
    observation_id: str | None = None, claim_id: str | None = None,
) -> Impact:
    if not (source_id or observation_id or claim_id):
        raise ValueError("name a source, an observation, or a claim")
    state = load_state(store, tenant)
    before = analyze(state)
    after = analyze(
        hypothetical(
            state,
            sources=[source_id] if source_id else [],
            observations=[observation_id] if observation_id else [],
            claims=[claim_id] if claim_id else [],
        )
    )
    return compare(state, before, after)


def apply_remediation(store: Store, tenant: str, labels: dict[str, Remediation]) -> None:
    if labels:
        store.write(
            tenant,
            "UNWIND $rows AS r MATCH (d:Decision {id: r.id}) SET d.remediation = r.value",
            {"rows": [{"id": key, "value": str(value)} for key, value in labels.items()]},
        )


def run_with_impact(store: Store, tenant: str, safety_write) -> tuple[str, Impact]:
    state = load_state(store, tenant)
    before = analyze(state)
    incident_id = safety_write()
    after = recompute(store, tenant)
    impact = compare(state, before, after)
    apply_remediation(store, tenant, impact.decisions)
    store.write(
        tenant,
        "MATCH (i:Incident {id: $id}) SET i.result = $result",
        {"id": incident_id, "result": json.dumps(impact.as_dict(), sort_keys=True)},
    )
    return incident_id, impact
