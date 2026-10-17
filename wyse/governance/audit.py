import json
from collections import defaultdict

from wyse.belief.support import Analysis, PossibleTruncation, State, analyze, load_state
from wyse.db import Store


def list_incidents(store: Store, tenant: str) -> list[dict]:
    rows = store.read(
        tenant,
        "MATCH (i:Incident) RETURN i.id AS id, i.kind AS kind, i.reason AS reason, "
        "i.created_at AS created_at, i.target AS target, i.result AS result "
        "ORDER BY created_at, id",
    )
    if len(rows) >= store.result_cap():
        raise PossibleTruncation("incident log reached the result cap")
    return [
        {**row, "result": json.loads(row["result"]) if row["result"] else None}
        for row in rows
    ]


def build_tree(state: State, analysis: Analysis, claim_id: str, max_depth: int = 8):
    by_claim = defaultdict(list)
    for j in state.justifications:
        by_claim[j.claim].append(j)
    seen: set[str] = set()
    cut = False

    def claim_node(cid: str, depth: int) -> dict:
        nonlocal cut
        meta = state.claim_meta[cid]
        node = {
            "type": "claim",
            "id": cid,
            "statement": {
                "subject": meta["subject"], "predicate": meta["predicate"], "object": meta["object"],
            },
            "belief": analysis.belief[cid],
        }
        if cid in seen:
            node["repeated"] = True
            return node
        seen.add(cid)
        if depth >= max_depth:
            cut = True
            node["justifications"] = None
            return node
        node["justifications"] = [
            {
                "id": j.id,
                "state": analysis.justification_state[j.id],
                "premises": [premise_node(p, depth + 1) for p in j.premises],
            }
            for j in by_claim.get(cid, [])
        ]
        return node

    def premise_node(pid: str, depth: int) -> dict:
        if pid in state.claims:
            return claim_node(pid, depth)
        row = state.observations.get(pid)
        return {
            "type": "observation",
            "id": pid,
            "valid": pid in analysis.grounded,
            "source": row["source"] if row else None,
        }

    return claim_node(claim_id, 0), cut


def observation_nodes(node: dict):
    if node["type"] == "observation":
        yield node
        return
    for justification in node.get("justifications") or []:
        for premise in justification["premises"]:
            yield from observation_nodes(premise)


def explain_belief(store: Store, tenant: str, claim_id: str, max_depth: int = 8) -> dict:
    state = load_state(store, tenant)
    if claim_id not in state.claims:
        raise ValueError(f"unknown claim: {claim_id}")
    analysis = analyze(state)
    tree, cut = build_tree(state, analysis, claim_id, max_depth)

    nodes = list(observation_nodes(tree))
    ids = sorted({node["id"] for node in nodes})
    details: dict[str, dict] = {}
    if ids:
        rows = store.read(
            tenant,
            "MATCH (s:Source)-[:CAPTURED_AS]->(o:Observation) WHERE o.id IN $ids "
            "RETURN o.id AS id, o.content AS content, s.name AS source",
            {"ids": ids},
        )
        details = {row["id"]: row for row in rows}
    for node in nodes:
        row = details.get(node["id"])
        if row:
            node["source_name"] = row["source"]
            if node["valid"]:
                node["content"] = row["content"]

    meta = state.claim_meta[claim_id]
    return {
        "claim_id": claim_id,
        "statement": {"subject": meta["subject"], "predicate": meta["predicate"], "object": meta["object"]},
        "belief": analysis.belief[claim_id],
        "usable": claim_id in analysis.usable,
        "truncated": cut,
        "tree": tree,
    }
