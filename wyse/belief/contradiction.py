from collections import defaultdict
from collections.abc import Iterable, Mapping

from wyse.db import Store


def resolve(
    supported: Iterable[str],
    links: Iterable[tuple[str, str]],
    rank: Mapping[str, tuple[int, int]],
) -> set[str]:
    members = set(supported)
    parent = {claim: claim for claim in members}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    for a, b in links:
        if a in parent and b in parent:
            parent[find(a)] = find(b)

    groups: dict[str, list[str]] = defaultdict(list)
    for claim in members:
        groups[find(claim)].append(claim)

    contested: set[str] = set()
    for group in groups.values():
        if len(group) < 2:
            continue
        best = max(rank[claim] for claim in group)
        leaders = [claim for claim in group if rank[claim] == best]
        if len(leaders) == 1:
            contested.update(claim for claim in group if claim != leaders[0])
        else:
            contested.update(group)
    return contested


def link_contradictions(
    store: Store, tenant: str, claim_id: str, subject: str, predicate: str, obj: str
) -> int:
    rows = store.read(
        tenant,
        "MATCH (o:Claim {subject: $s, predicate: $p}) "
        "WHERE o.object <> $o AND o.id <> $cid RETURN o.id AS id",
        {"s": subject, "p": predicate, "o": obj, "cid": claim_id},
    )
    pairs = [{"a": min(claim_id, r["id"]), "b": max(claim_id, r["id"])} for r in rows]
    if pairs:
        store.write(
            tenant,
            "UNWIND $pairs AS p MATCH (a:Claim {id: p.a}), (b:Claim {id: p.b}) "
            "MERGE (a)-[:CONTRADICTS]->(b)",
            {"pairs": pairs},
        )
    return len(pairs)
