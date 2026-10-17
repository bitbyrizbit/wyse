from collections import defaultdict
from dataclasses import dataclass

from wyse.belief.policy import normalize
from wyse.belief.support import Analysis, State, analyze, load_state
from wyse.db import Store
from wyse.ids import now_ms


@dataclass
class Recall:
    as_of: int
    usable: list[dict]
    contested: list[dict]
    withheld: list[dict]


def select(state: State, subject, predicate, claim_ids) -> list[str]:
    wanted = set(claim_ids) if claim_ids is not None else None
    subj = normalize(subject) if subject else None
    pred = normalize(predicate) if predicate else None
    picked = []
    for cid, meta in state.claim_meta.items():
        if wanted is not None and cid not in wanted:
            continue
        if subj and meta["subject"] != subj:
            continue
        if pred and meta["predicate"] != pred:
            continue
        picked.append(cid)
    return picked


def depends_on_contested(claim_id: str, state: State, analysis: Analysis) -> bool:
    by_claim: dict[str, list] = defaultdict(list)
    for j in state.justifications:
        if analysis.justification_state[j.id] == "VALID":
            by_claim[j.claim].append(j)
    seen = {claim_id}
    stack = [claim_id]
    while stack:
        current = stack.pop()
        for j in by_claim.get(current, ()):
            for premise in j.premises:
                if premise in state.claims and premise not in seen:
                    if analysis.belief[premise] == "CONTESTED":
                        return True
                    seen.add(premise)
                    stack.append(premise)
    return False


def _reason(meta: dict, belief: str) -> str:
    if belief in ("UNSUPPORTED", "RETRACTED"):
        return belief
    if meta["use"] in ("QUARANTINED", "RESTRICTED"):
        return meta["use"]
    return "BLOCKED_BY_QUARANTINE"


def assemble(state: State, analysis: Analysis, selected: list[str], as_of: int) -> Recall:
    neighbors: dict[str, set[str]] = defaultdict(set)
    for a, b in state.conflicts:
        neighbors[a].add(b)
        neighbors[b].add(a)

    usable: list[dict] = []
    contested: list[dict] = []
    withheld: list[dict] = []
    for cid in sorted(selected):
        meta = state.claim_meta[cid]
        belief = analysis.belief[cid]
        if belief not in ("SUPPORTED", "CONTESTED") or cid not in analysis.use_ok:
            withheld.append({"claim_id": cid, "belief_status": belief, "reason": _reason(meta, belief)})
            continue
        item = {
            "claim_id": cid,
            "statement": {
                "subject": meta["subject"], "predicate": meta["predicate"], "object": meta["object"],
            },
            "belief_status": belief,
            "revision": meta["revision"],
            "independent_sources": len(analysis.independent_sources.get(cid, ())),
            "evidence": sorted(analysis.roots.get(cid, ())),
            "conflicts": sorted(neighbors.get(cid, ())),
            "depends_on_contested": depends_on_contested(cid, state, analysis),
        }
        (usable if belief == "SUPPORTED" else contested).append(item)
    return Recall(as_of, usable, contested, withheld)


def recall(
    store: Store, tenant: str, *, subject: str | None = None,
    predicate: str | None = None, claim_ids: list[str] | None = None,
) -> Recall:
    state = load_state(store, tenant)
    analysis = analyze(state)
    return assemble(state, analysis, select(state, subject, predicate, claim_ids), now_ms())
