import time
import json
from dataclasses import dataclass

from wyse.belief.contradiction import resolve
from wyse.belief.core import Justif, evaluate
from wyse.belief.independence import independent_sources, propagate_roots
from wyse.belief.policy import rank_of
from wyse.db import Store

PAGE = 5000
LOAD_TIMEOUT_MS = 30_000
BLOCKING_USE = ("QUARANTINED", "RESTRICTED")


class PossibleTruncation(RuntimeError):
    pass


@dataclass
class State:
    claims: dict[str, str]
    claim_meta: dict[str, dict]
    observations: dict[str, dict]
    justifications: list[Justif]
    justification_state: dict[str, str]
    conflicts: list[tuple[str, str]]
    invalidated: set[str]
    decisions: dict[str, dict]


@dataclass
class Analysis:
    belief: dict[str, str]
    justification_state: dict[str, str]
    roots: dict[str, set[str]]
    independent_sources: dict[str, set[str]]
    rank: dict[str, tuple[int, int]]
    grounded: set[str]
    use_ok: set[str]
    usable: set[str]


def _load(store: Store, tenant: str, query: str, order: str) -> list[dict]:
    cap = store.result_cap()
    page = max(1, min(PAGE, cap // 2)) if cap > 0 else PAGE
    rows: list[dict] = []
    skip = 0
    while True:
        batch = store.read(
            tenant,
            f"{query} ORDER BY {order} SKIP {skip} LIMIT {page}",
            timeout_ms=LOAD_TIMEOUT_MS,
        )
        rows.extend(batch)
        if len(batch) < page:
            return rows
        skip += page


def load_state(store: Store, tenant: str) -> State:
    claim_rows = _load(
        store, tenant,
        "MATCH (c:Claim) RETURN c.id AS id, c.belief_status AS status, c.subject AS subject, "
        "c.predicate AS predicate, c.object AS object, c.use_status AS use, c.revision AS revision",
        "id",
    )
    observation_rows = _load(
        store, tenant,
        "MATCH (s:Source)-[:CAPTURED_AS]->(o:Observation) "
        "RETURN o.id AS id, s.id AS source, s.incident_state AS state, s.trust_tier AS tier",
        "id",
    )
    invalidated = {
        r["id"] for r in _load(
            store, tenant, "MATCH (:Incident)-[:INVALIDATED]->(x) RETURN DISTINCT x.id AS id", "id"
        )
    }
    justification_rows = _load(
        store, tenant,
        "MATCH (j:Justification)-[:JUSTIFIES]->(c:Claim) OPTIONAL MATCH (j)-[:REQUIRES]->(p) "
        "RETURN j.id AS id, j.state AS state, c.id AS claim, collect(p.id) AS premises",
        "id",
    )
    conflict_rows = _load(
        store, tenant,
        "MATCH (a:Claim)-[:CONTRADICTS]->(b:Claim) RETURN a.id AS a, b.id AS b",
        "a, b",
    )
    decision_rows = _load(
        store, tenant,
        "MATCH (d:Decision) OPTIONAL MATCH (d)-[:USED]->(c:Claim) "
        "RETURN d.id AS id, d.summary AS summary, d.decided_at AS decided_at, d.acted AS acted, "
        "d.remediation AS remediation, d.snapshot AS snapshot, collect(c.id) AS claims",
        "id",
    )
    return State(
        claims={r["id"]: r["status"] for r in claim_rows},
        claim_meta={
            r["id"]: {
                "subject": r["subject"], "predicate": r["predicate"], "object": r["object"],
                "use": r["use"], "revision": r["revision"],
            }
            for r in claim_rows
        },
        observations={
            r["id"]: {"source": r["source"], "state": r["state"], "tier": r["tier"]}
            for r in observation_rows
        },
        justifications=[Justif(r["id"], r["claim"], tuple(r["premises"])) for r in justification_rows],
        justification_state={r["id"]: r["state"] for r in justification_rows},
        conflicts=[(r["a"], r["b"]) for r in conflict_rows],
        invalidated=invalidated,
        decisions={
            r["id"]: {
                "summary": r["summary"],
                "decided_at": r["decided_at"],
                "claims": list(r["claims"]),
                "acted": bool(r["acted"]),
                "remediation": r["remediation"],
                "snapshot": json.loads(r["snapshot"]) if r["snapshot"] else None,
            }
            for r in decision_rows
        },
    )


def analyze(state: State) -> Analysis:
    source_of = {oid: row["source"] for oid, row in state.observations.items()}
    dead_sources = {row["source"] for row in state.observations.values() if row["state"] != "CLEAR"}
    dead_sources |= state.invalidated & set(source_of.values())
    grounded = {
        oid for oid, source in source_of.items()
        if source not in dead_sources and oid not in state.invalidated
    }
    retracted = {
        cid for cid, status in state.claims.items()
        if status == "RETRACTED" or cid in state.invalidated
    }

    supported, valid = evaluate(grounded, state.justifications, retracted)
    roots = propagate_roots([j for j in state.justifications if j.id in valid], grounded)

    tier_of = {oid: rank_of(row["tier"]) for oid, row in state.observations.items()}
    sources: dict[str, set[str]] = {}
    rank: dict[str, tuple[int, int]] = {}
    for cid in supported:
        found = roots.get(cid, set())
        sources[cid] = independent_sources(found, source_of)
        rank[cid] = (max((tier_of[r] for r in found), default=0), len(sources[cid]))

    contested = resolve(supported, state.conflicts, rank)

    held_back = retracted | {
        cid for cid, meta in state.claim_meta.items() if meta["use"] in BLOCKING_USE
    }
    cleared, _ = evaluate(grounded, state.justifications, held_back)
    use_ok = supported & cleared
    usable = use_ok - contested

    belief: dict[str, str] = {}
    for cid in state.claims:
        if cid in retracted:
            belief[cid] = "RETRACTED"
        elif cid in contested:
            belief[cid] = "CONTESTED"
        elif cid in supported:
            belief[cid] = "SUPPORTED"
        else:
            belief[cid] = "UNSUPPORTED"

    return Analysis(
        belief=belief,
        justification_state={j.id: "VALID" if j.id in valid else "INVALID" for j in state.justifications},
        roots=roots,
        independent_sources=sources,
        rank=rank,
        grounded=grounded,
        use_ok=use_ok,
        usable=usable,
    )


def _persist(store: Store, tenant: str, state: State, result: Analysis) -> bool:
    changes = [
        {"id": cid, "old": state.claims[cid], "status": status}
        for cid, status in result.belief.items()
        if state.claims[cid] != status
    ]
    if changes:
        rows = store.write(
            tenant,
            "UNWIND $rows AS r MATCH (c:Claim {id: r.id}) WHERE c.belief_status = r.old "
            "SET c.belief_status = r.status, c.revision = c.revision + 1 "
            "RETURN count(c) AS n",
            {"rows": changes},
        )
        if rows[0]["n"] != len(changes):
            return False

    flips = [
        {"id": jid, "old": state.justification_state.get(jid), "state": value}
        for jid, value in result.justification_state.items()
        if state.justification_state.get(jid) != value
    ]
    if flips:
        rows = store.write(
            tenant,
            "UNWIND $rows AS r MATCH (j:Justification {id: r.id}) WHERE j.state = r.old "
            "SET j.state = r.state RETURN count(j) AS n",
            {"rows": flips},
        )
        if rows[0]["n"] != len(flips):
            return False
    return True


def recompute(store: Store, tenant: str, attempts: int = 10) -> Analysis:
    for attempt in range(attempts):
        state = load_state(store, tenant)
        result = analyze(state)
        if _persist(store, tenant, state, result):
            return result
        time.sleep(0.01 * (attempt + 1))
    raise RuntimeError("belief state kept changing during recompute")
