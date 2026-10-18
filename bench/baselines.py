import time
from dataclasses import dataclass

from bench.oracle import basis
from bench.scenarios import Scenario


@dataclass
class Result:
    withdrawn: set[str]
    flagged: dict[str, str]
    seconds: float = 0.0
    recall_seconds: float = 0.0


class Plain:
    name = "Plain memory"

    def load(self, scenario: Scenario) -> None:
        self.direct = {
            cid: {proof.source for proof in proofs if proof.source is not None}
            for cid, proofs in scenario.claims.items()
        }

    def compromise(self, reported: list[str]) -> Result:
        started = time.perf_counter()
        gone = set(reported)
        withdrawn = {cid for cid, srcs in self.direct.items() if srcs and not (srcs - gone)}
        return Result(withdrawn, {}, time.perf_counter() - started)

    def close(self) -> None:
        pass


class Cascade:
    name = "Delete-cascade"

    def load(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.roots = basis(scenario)

    def compromise(self, reported: list[str]) -> Result:
        started = time.perf_counter()
        gone = set(reported)
        withdrawn = {cid for cid, roots in self.roots.items() if roots & gone}
        flagged = {
            decision.id: "CORRECTION"
            for decision in self.scenario.decisions
            if any(cid in withdrawn for cid in decision.claims)
        }
        return Result(withdrawn, flagged, time.perf_counter() - started)

    def close(self) -> None:
        pass
