from bench.scenarios import Scenario


def supported_claims(scenario: Scenario, bad: set[str]) -> set[str]:
    holds: set[str] = set()
    for cid, proofs in scenario.claims.items():
        for proof in proofs:
            if proof.source is not None:
                ok = proof.source not in bad
            else:
                ok = all(parent in holds for parent in proof.parents)
            if ok:
                holds.add(cid)
                break
    return holds


def basis(scenario: Scenario) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for cid, proofs in scenario.claims.items():
        sources: set[str] = set()
        for proof in proofs:
            if proof.source is not None:
                sources.add(proof.source)
            else:
                for parent in proof.parents:
                    sources |= found[parent]
        found[cid] = sources
    return found


def expected_flags(scenario: Scenario) -> dict[str, str]:
    bad = scenario.truth_bad
    alive = supported_claims(scenario, bad)
    roots = basis(scenario)
    flags: dict[str, str] = {}
    for decision in scenario.decisions:
        if any(cid not in alive for cid in decision.claims):
            flags[decision.id] = "CORRECTION"
        elif any(roots[cid] & bad for cid in decision.claims):
            flags[decision.id] = "REVIEW"
    return flags
