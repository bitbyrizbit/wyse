import re
from collections.abc import Iterable

from wyse.belief.policy import digest, normalize
from wyse.db import Store

PREMISE_PATTERN = re.compile(r"(obs|clm)_[0-9a-f]{16}")

ATTACH = """
MERGE (c:Claim {id: $cid})
  ON CREATE SET c.tenant = $tenant, c.subject = $subject, c.predicate = $predicate,
                c.object = $object, c.created_at = $now, c.revision = 1,
                c.belief_status = 'UNSUPPORTED', c.use_status = 'ELIGIBLE'
MERGE (j:Justification {id: $jid})
  ON CREATE SET j.tenant = $tenant, j.rule = $rule, j.state = 'INVALID'
MERGE (j)-[:JUSTIFIES]->(c)
WITH j
MATCH (p) WHERE p.id IN $premises
MERGE (j)-[:REQUIRES]->(p)
RETURN count(p) AS linked
"""


def claim_id_for(subject: str, predicate: str, obj: str) -> str:
    return "clm_" + digest(normalize(subject), normalize(predicate), normalize(obj))


def justification_id_for(claim_id: str, premises: Iterable[str]) -> str:
    return "jst_" + digest(claim_id, *sorted(set(premises)))


def ensure_premises_exist(store: Store, tenant: str, premises: Iterable[str]) -> None:
    wanted = set(premises)
    rows = store.read(tenant, "MATCH (p) WHERE p.id IN $ids RETURN p.id AS id", {"ids": sorted(wanted)})
    missing = wanted - {row["id"] for row in rows}
    if missing:
        raise ValueError(f"unknown premises: {sorted(missing)}")


def attach(
    store: Store, tenant: str, claim_id: str, subject: str, predicate: str,
    obj: str, premises: tuple[str, ...], rule: str, now: int,
) -> None:
    rows = store.write(
        tenant,
        ATTACH,
        {
            "cid": claim_id,
            "jid": justification_id_for(claim_id, premises),
            "tenant": tenant,
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "rule": rule,
            "now": now,
            "premises": list(premises),
        },
    )
    if rows[0]["linked"] != len(premises):
        raise RuntimeError("justification was written with missing premises")
