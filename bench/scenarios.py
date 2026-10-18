import random
from dataclasses import dataclass

KINDS = ("tool", "web", "agent")


@dataclass(frozen=True)
class Proof:
    source: str | None = None
    parents: tuple[str, ...] = ()


@dataclass
class Decision:
    id: str
    claims: tuple[str, ...]
    acted: bool


@dataclass
class Scenario:
    seed: int
    sources: dict[str, str]
    mirrors: dict[str, str]
    claims: dict[str, list[Proof]]
    decisions: list[Decision]
    reported: list[str]

    @property
    def truth_bad(self) -> set[str]:
        bad = set(self.reported)
        bad |= {self.mirrors[name] for name in self.reported if name in self.mirrors}
        return bad


def generate(
    seed: int, *, n_sources: int = 12, n_base: int = 40, n_derived: int = 30,
    n_decisions: int = 20, n_reported: int = 3, mirror_rate: float = 0.0,
) -> Scenario:
    rng = random.Random(seed)
    names = [f"s{i}" for i in range(n_sources)]
    sources = {name: KINDS[i % len(KINDS)] for i, name in enumerate(names)}
    mirrors: dict[str, str] = {}
    claims: dict[str, list[Proof]] = {}

    for i in range(n_base):
        chosen = rng.sample(names, rng.choice((1, 1, 2, 3)))
        primary = chosen[0]
        used = {primary}
        proofs = [Proof(source=primary)]
        for other in chosen[1:]:
            twin = f"m_{primary}"
            if rng.random() < mirror_rate and twin not in used:
                mirrors[primary] = twin
                sources[twin] = sources[primary]
                pick = twin
            else:
                pick = other
            used.add(pick)
            proofs.append(Proof(source=pick))
        claims[f"c{i}"] = proofs

    known = list(claims)
    for _ in range(n_derived):
        proofs = []
        for _ in range(rng.choice((1, 1, 2))):
            width = min(len(known), rng.choice((2, 2, 3)))
            proofs.append(Proof(parents=tuple(sorted(rng.sample(known, width)))))
        cid = f"c{len(claims)}"
        claims[cid] = list(dict.fromkeys(proofs))
        known.append(cid)

    decisions = [
        Decision(
            f"d{k}",
            tuple(sorted(rng.sample(known, rng.choice((1, 2, 3))))),
            rng.random() < 0.4,
        )
        for k in range(n_decisions)
    ]
    return Scenario(seed, sources, mirrors, claims, decisions, rng.sample(names, n_reported))
