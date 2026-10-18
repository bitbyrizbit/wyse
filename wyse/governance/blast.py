from wyse.db import Store

FROM_SOURCE = (
    "MATCH (:Source {id: $id})-[:CAPTURED_AS]->(:Observation)<-[:REQUIRES]-"
    "(:Justification)-[:JUSTIFIES]->(c:Claim) RETURN DISTINCT c.id AS id"
)
FROM_OBSERVATION = (
    "MATCH (:Observation {id: $id})<-[:REQUIRES]-(:Justification)-[:JUSTIFIES]->(c:Claim) "
    "RETURN DISTINCT c.id AS id"
)
NEXT_LEVEL = (
    "UNWIND $ids AS cid MATCH (:Claim {id: cid})<-[:REQUIRES]-(:Justification)"
    "-[:JUSTIFIES]->(d:Claim) RETURN DISTINCT d.id AS id"
)
DECISIONS = "MATCH (d:Decision)-[:USED]->(c:Claim) WHERE c.id IN $ids RETURN DISTINCT d.id AS id"


def blast_radius(
    store: Store, tenant: str, *, source_id: str | None = None,
    observation_id: str | None = None, claim_id: str | None = None, max_depth: int = 25,
) -> dict:
    if source_id:
        seed = [row["id"] for row in store.read(tenant, FROM_SOURCE, {"id": source_id})]
    elif observation_id:
        seed = [row["id"] for row in store.read(tenant, FROM_OBSERVATION, {"id": observation_id})]
    elif claim_id:
        seed = [claim_id]
    else:
        raise ValueError("name a source, an observation, or a claim")

    cap = store.result_cap()
    reached = {cid: 0 for cid in seed}
    frontier = list(seed)
    depth = 0
    truncated = False
    while frontier:
        depth += 1
        if depth > max_depth:
            truncated = True
            break
        rows = store.read(tenant, NEXT_LEVEL, {"ids": frontier})
        if len(rows) >= cap:
            truncated = True
            break
        frontier = [row["id"] for row in rows if row["id"] not in reached]
        for cid in frontier:
            reached[cid] = depth

    decisions: list[str] = []
    if reached:
        rows = store.read(tenant, DECISIONS, {"ids": sorted(reached)})
        decisions = sorted(row["id"] for row in rows)
    return {
        "claims": sorted(reached),
        "depth": max(reached.values(), default=0),
        "decisions": decisions,
        "truncated": truncated,
    }
