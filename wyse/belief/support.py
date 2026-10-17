from dataclasses import dataclass

from wyse.belief.contradiction import resolve
from wyse.belief.core import Justif, evaluate
from wyse.belief.independence import independent_sources, propagate_roots
from wyse.belief.policy import rank_of
from wyse.db import Store

ROW_CAP = 10_000
LOAD_TIMEOUT_MS = 30_000


class PossibleTruncation(RuntimeError):
    pass


@dataclass
class State:
    claims: dict[str, str]
    observations: dict[str, dict]
    justifications: list[Justif]
    justification_state: dict[str, str]
    conflicts: list[tuple[str, str]]
    invalidated: set[str]


@dataclass
class Analysis:
    belief: dict[str, str]
    justification_state: dict[str, str]
    roots: dict[str, set[str]]
    independent_sources: dict[str, set[str]]
    rank: dict[str, tuple[int, int]]


def _load(store: Store, tenant: str, cypher: str) -> list[dict]:
    rows = store.read(tenant, cypher, timeout_ms=LOAD_TIMEOUT_MS)
    if len(rows) >= ROW_CAP:
        raise PossibleTruncation(f"query returned {len(rows)} rows, at the result cap: {cypher[:60]}")
    return rows


def load_state(store: Store, tenant: str) -> State:
    claims = {
        r["id"]: r["status"]
        for r in _load(store, tenant, "MATCH (c:Claim) RETURN c.id AS id, c.belief_status AS status")
    }
    observations = {
        r["id"]: {"source": r["source"], "state": r["state"], "tier": r["tier"]}
        for r in _load(
            store,
            tenant,
            "MATCH (s:Source)-[:CAPTURED_AS]->(o:Observation) "
            "RETURN o.id AS id, s.id AS source, s.incident_state AS state, s.trust_tier AS tier",
        )
    }
    invalidated = {
        r["id"] for r in _load(store, tenant, "MATCH (:Incident)-[:INVALIDATED]->(x) RETURN x.id AS id")
    }
    rows = _load(
        store,
        tenant,
        "MATCH (j:Justification)-[:JUSTIFIES]->(c:Claim) "
        "OPTIONAL MATCH (j)-[:REQUIRES]->(p) "
        "RETURN j.id AS id, j.state AS state, c.id AS claim, collect(p.id) AS premises",
    )
    conflicts = [
        (r["a"], r["b"])
        for r in _load(store, tenant, "MATCH (a:Claim)-[:CONTRADICTS]->(b:Claim) RETURN a.id AS a, b.id AS b")
    ]
    return State(
        claims=claims,
        observations=observations,
        justifications=[Justif(r["id"], r["claim"], tuple(r["premises"])) for r in rows],
        justification_state={r["id"]: r["state"] for r in rows},
        conflicts=conflicts,
        invalidated=invalidated,
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
    )


def recompute(store: Store, tenant: str) -> Analysis:
    state = load_state(store, tenant)
    result = analyze(state)

    claim_changes = [
        {"id": cid, "status": status}
        for cid, status in result.belief.items()
        if state.claims[cid] != status
    ]
    if claim_changes:
        store.write(
            tenant,
            "UNWIND $rows AS r MATCH (c:Claim {id: r.id}) "
            "SET c.belief_status = r.status, c.revision = c.revision + 1",
            {"rows": claim_changes},
        )

    justification_changes = [
        {"id": jid, "state": value}
        for jid, value in result.justification_state.items()
        if state.justification_state.get(jid) != value
    ]
    if justification_changes:
        store.write(
            tenant,
            "UNWIND $rows AS r MATCH (j:Justification {id: r.id}) SET j.state = r.state",
            {"rows": justification_changes},
        )
    return result
