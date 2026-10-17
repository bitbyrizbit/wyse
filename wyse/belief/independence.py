from collections import defaultdict
from collections.abc import Iterable, Mapping

from wyse.belief.core import Justif


def propagate_roots(valid: Iterable[Justif], grounded: Iterable[str]) -> dict[str, set[str]]:
    valid = list(valid)
    roots: dict[str, set[str]] = defaultdict(set)
    for obs in grounded:
        roots[obs].add(obs)
    changed = True
    while changed:
        changed = False
        for j in valid:
            incoming: set[str] = set()
            for premise in j.premises:
                incoming |= roots.get(premise, set())
            target = roots[j.claim]
            if not incoming <= target:
                target |= incoming
                changed = True
    return dict(roots)


def independent_sources(roots: Iterable[str], source_of: Mapping[str, str]) -> set[str]:
    return {source_of[root] for root in roots}
