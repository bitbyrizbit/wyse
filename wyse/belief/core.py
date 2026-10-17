from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Justif:
    id: str
    claim: str
    premises: tuple[str, ...]


def evaluate(
    grounded: Iterable[str],
    justifications: Iterable[Justif],
    blocked: Iterable[str] = (),
) -> tuple[set[str], set[str]]:
    blocked = set(blocked)
    waiting: dict[str, int] = {}
    feeds: dict[str, list[Justif]] = defaultdict(list)
    for j in justifications:
        needs = set(j.premises)
        if not needs:
            continue
        waiting[j.id] = len(needs)
        for premise in needs:
            feeds[premise].append(j)

    truth = set(grounded)
    queue = deque(truth)
    supported: set[str] = set()
    valid: set[str] = set()
    while queue:
        item = queue.popleft()
        for j in feeds.get(item, ()):
            waiting[j.id] -= 1
            if waiting[j.id] == 0:
                valid.add(j.id)
                if j.claim not in truth and j.claim not in blocked:
                    truth.add(j.claim)
                    supported.add(j.claim)
                    queue.append(j.claim)
    return supported, valid
