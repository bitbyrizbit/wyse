import json
from collections import defaultdict
from dataclasses import dataclass, field

from wyse.agents.scopes import scratch_scope
from wyse.belief.contradiction import link_contradictions
from wyse.belief.justify import attach
from wyse.belief.policy import MAX_FIELD, TRUST_RANK, check_text, rank_of
from wyse.belief.support import Analysis, PossibleTruncation, State, analyze, load_state, recompute
from wyse.db import Store
from wyse.governance.retract import retract_claim
from wyse.ids import new_id, now_ms
from wyse.models import TrustTier

OBSERVATIONS = (
    "MATCH (s:Source)-[:CAPTURED_AS]->(o:Observation) WHERE o.id IN $ids "
    "RETURN s.id AS sid, s.kind AS kind, s.name AS name, s.trust_tier AS tier, o.id AS id, "
    "o.content AS content, o.content_hash AS hash, o.observed_at AS observed, "
    "o.recorded_at AS recorded"
)

COPY_EVIDENCE = """
UNWIND $rows AS r
MERGE (s:Source {id: r.sid})
  ON CREATE SET s.tenant = $tenant, s.kind = r.kind, s.name = r.name,
                s.trust_tier = r.tier, s.incident_state = 'CLEAR'
MERGE (o:Observation {id: r.id})
  ON CREATE SET o.tenant = $tenant, o.content = r.content, o.content_hash = r.hash,
                o.observed_at = r.observed, o.recorded_at = r.recorded
MERGE (s)-[:CAPTURED_AS]->(o)
"""

COPY_CLAIMS = """
UNWIND $rows AS r
MERGE (c:Claim {id: r.id})
  ON CREATE SET c.tenant = $tenant, c.subject = r.subject, c.predicate = r.predicate,
                c.object = r.object, c.created_at = $now, c.revision = 1,
                c.belief_status = 'UNSUPPORTED', c.use_status = 'ELIGIBLE'
"""

RECORD_PROMOTION = """
MERGE (a:Agent {id: $aid})
  ON CREATE SET a.tenant = $tenant, a.role = 'agent', a.scope = 'shared'
CREATE (p:Promotion {id: $pid, tenant: $tenant, agent: $aid, scope: $scope,
                     at: $now, claims: $claims})
CREATE (a)-[:MADE]->(p)
WITH p
UNWIND $ids AS cid
MATCH (c:Claim {id: cid})
CREATE (p)-[:PROMOTED]->(c)
RETURN count(c) AS n
"""


@dataclass(frozen=True)
class Policy:
    max_tier: TrustTier = TrustTier.TOOL


@dataclass
class Outcome:
    promotion_id: str | None
    promoted: list[str]
    held: dict[str, str]
    shared: dict[str, str] = field(default_factory=dict)


def cap_tier(tier: str, ceiling: TrustTier) -> str:
    return str(tier) if rank_of(tier) <= TRUST_RANK[ceiling] else str(ceiling)


def closure(state: State, analysis: Analysis, roots: list[str]):
    by_claim = defaultdict(list)
    for j in state.justifications:
        if analysis.justification_state[j.id] != "VALID":
            continue
        if all(p in analysis.grounded or p in analysis.use_ok for p in j.premises):
            by_claim[j.claim].append(j)
    claims: set[str] = set()
    justs: dict[str, object] = {}
    observations: set[str] = set()
    stack = list(roots)
    while stack:
        cid = stack.pop()
        if cid in claims:
            continue
        claims.add(cid)
        for j in by_claim.get(cid, ()):
            justs[j.id] = j
            for premise in j.premises:
                if premise in state.claims:
                    stack.append(premise)
                else:
                    observations.add(premise)
    return claims, justs, observations


def promote(
    store: Store, tenant: str, agent: str, claim_ids: list[str], policy: Policy = Policy(),
) -> Outcome:
    scope = scratch_scope(tenant, agent)
    if scope not in store.list_tenants():
        raise ValueError(f"agent {agent!r} has no scratch scope")

    source = load_state(store, scope)
    mine = analyze(source)
    shared = load_state(store, tenant)
    theirs = analyze(shared)
    ceiling = TRUST_RANK[policy.max_tier]

    held: dict[str, str] = {}
    accepted: list[str] = []
    for cid in sorted(set(claim_ids)):
        if cid not in source.claims:
            held[cid] = "UNKNOWN"
            continue
        if cid not in mine.usable:
            held[cid] = mine.belief[cid] if mine.belief[cid] != "SUPPORTED" else "BLOCKED"
            continue
        meta = source.claim_meta[cid]
        tier, count = mine.rank[cid]
        incoming = (min(tier, ceiling), count)
        rivals = [
            theirs.rank[other]
            for other, row in shared.claim_meta.items()
            if row["subject"] == meta["subject"] and row["predicate"] == meta["predicate"]
            and row["object"] != meta["object"] and other in theirs.use_ok
        ]
        if rivals and incoming <= max(rivals):
            held[cid] = "CONFLICT"
            continue
        accepted.append(cid)
    if not accepted:
        return Outcome(None, [], held)

    claims, justs, observation_ids = closure(source, mine, accepted)
    evidence = store.read(scope, OBSERVATIONS, {"ids": sorted(observation_ids)})
    if len(evidence) >= store.result_cap():
        raise PossibleTruncation("promotion evidence reached the result cap")
    rule_rows = store.read(
        scope,
        "MATCH (j:Justification) WHERE j.id IN $ids RETURN j.id AS id, j.rule AS rule",
        {"ids": sorted(justs)},
    )
    rules = {row["id"]: row["rule"] for row in rule_rows}

    now = now_ms()
    store.write(
        tenant, COPY_EVIDENCE,
        {
            "tenant": tenant,
            "rows": [{**row, "tier": cap_tier(row["tier"], policy.max_tier)} for row in evidence],
        },
    )
    store.write(
        tenant, COPY_CLAIMS,
        {
            "tenant": tenant, "now": now,
            "rows": [
                {"id": cid, **{key: source.claim_meta[cid][key] for key in ("subject", "predicate", "object")}}
                for cid in sorted(claims)
            ],
        },
    )
    for j in justs.values():
        meta = source.claim_meta[j.claim]
        attach(
            store, tenant, j.claim, meta["subject"], meta["predicate"], meta["object"],
            tuple(sorted(set(j.premises))), rules.get(j.id) or "promoted", now,
        )

    promotion_id = new_id("prm")
    written = store.write(
        tenant, RECORD_PROMOTION,
        {
            "aid": check_text("agent", agent, MAX_FIELD), "pid": promotion_id, "tenant": tenant,
            "scope": scope, "now": now, "claims": json.dumps(sorted(claims)), "ids": accepted,
        },
    )
    if written[0]["n"] != len(accepted):
        raise RuntimeError("promotion record was written with missing claims")

    for cid in sorted(claims):
        meta = source.claim_meta[cid]
        link_contradictions(store, tenant, cid, meta["subject"], meta["predicate"], meta["object"])
    result = recompute(store, tenant)
    return Outcome(promotion_id, accepted, held, {cid: result.belief[cid] for cid in accepted})


def revoke_promotion(store: Store, tenant: str, promotion_id: str, reason: str) -> list[str]:
    rows = store.read(
        tenant,
        "MATCH (:Promotion {id: $id})-[:PROMOTED]->(c:Claim) RETURN c.id AS id ORDER BY id",
        {"id": promotion_id},
    )
    if not rows:
        raise ValueError(f"unknown promotion: {promotion_id}")
    incidents = []
    for row in rows:
        try:
            incident_id, _ = retract_claim(store, tenant, row["id"], reason)
        except ValueError:
            continue
        incidents.append(incident_id)
    return incidents
