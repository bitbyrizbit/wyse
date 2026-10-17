from collections.abc import Sequence
from typing import NamedTuple

from wyse.belief.contradiction import link_contradictions
from wyse.belief.justify import (
    PREMISE_PATTERN, attach, claim_id_for, ensure_premises_exist,
)
from wyse.belief.policy import (
    MAX_CONTENT, MAX_FIELD, check_text, content_hash, normalize,
    source_id_for, tier_for_kind,
)
from wyse.belief.support import recompute
from wyse.db import Store
from wyse.ids import new_id, now_ms

RECORD = """
MERGE (s:Source {id: $sid})
  ON CREATE SET s.tenant = $tenant, s.kind = $kind, s.name = $name,
                s.trust_tier = $tier, s.incident_state = 'CLEAR'
CREATE (o:Observation {id: $oid, tenant: $tenant, content: $content,
                       content_hash: $hash, observed_at: $observed, recorded_at: $now})
CREATE (s)-[:CAPTURED_AS]->(o)
"""

PROPOSER = """
MERGE (a:Agent {id: $aid})
  ON CREATE SET a.tenant = $tenant, a.role = 'agent', a.scope = 'private'
WITH a
MATCH (c:Claim {id: $cid})
MERGE (a)-[:PROPOSED]->(c)
"""


class Recorded(NamedTuple):
    source_id: str
    observation_id: str


class Remembered(NamedTuple):
    claim_id: str
    observation_id: str
    source_id: str


def record_observation(
    store: Store, tenant: str, *, source_kind: str, source_name: str,
    content: str, observed_at: int | None = None,
) -> Recorded:
    kind = check_text("source_kind", source_kind, MAX_FIELD).lower()
    name = check_text("source_name", source_name, MAX_FIELD)
    body = check_text("content", content, MAX_CONTENT)
    now = now_ms()
    source_id = source_id_for(kind, name)
    observation_id = new_id("obs")
    store.write(
        tenant,
        RECORD,
        {
            "sid": source_id,
            "oid": observation_id,
            "tenant": tenant,
            "kind": kind,
            "name": name,
            "tier": str(tier_for_kind(kind)),
            "content": body,
            "hash": content_hash(body),
            "observed": observed_at if observed_at is not None else now,
            "now": now,
        },
    )
    return Recorded(source_id, observation_id)


def assert_claim(
    store: Store, tenant: str, *, subject: str, predicate: str, object: str,
    evidence: Sequence[Sequence[str]], rule: str = "direct",
    exclusive: bool = True, agent_id: str | None = None,
    recompute_now: bool = True,
) -> str:
    subj = normalize(check_text("subject", subject, MAX_FIELD))
    pred = normalize(check_text("predicate", predicate, MAX_FIELD))
    obj = normalize(check_text("object", object, MAX_FIELD))
    claim_id = claim_id_for(subj, pred, obj)

    groups = [tuple(sorted(set(group))) for group in evidence]
    if not groups or any(not group for group in groups):
        raise ValueError("every claim needs at least one non-empty evidence set")
    flat = {premise for group in groups for premise in group}
    for premise in flat:
        if not PREMISE_PATTERN.fullmatch(premise):
            raise ValueError(f"malformed premise id: {premise!r}")
    if claim_id in flat:
        raise ValueError("a claim cannot justify itself")
    ensure_premises_exist(store, tenant, flat)

    now = now_ms()
    for group in groups:
        attach(store, tenant, claim_id, subj, pred, obj, group, rule, now)
    if agent_id:
        store.write(
            tenant, PROPOSER,
            {"aid": check_text("agent_id", agent_id, MAX_FIELD), "tenant": tenant, "cid": claim_id},
        )
    if exclusive:
        link_contradictions(store, tenant, claim_id, subj, pred, obj)
    if recompute_now:
        recompute(store, tenant)
    return claim_id


def remember(
    store: Store, tenant: str, *, source_kind: str, source_name: str,
    content: str, subject: str, predicate: str, object: str,
    agent_id: str | None = None, exclusive: bool = True,
) -> Remembered:
    recorded = record_observation(
        store, tenant, source_kind=source_kind, source_name=source_name, content=content,
    )
    claim_id = assert_claim(
        store, tenant, subject=subject, predicate=predicate, object=object,
        evidence=[[recorded.observation_id]], agent_id=agent_id, exclusive=exclusive,
    )
    return Remembered(claim_id, recorded.observation_id, recorded.source_id)
