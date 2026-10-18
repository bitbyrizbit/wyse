from bench.baselines import Result
from bench.oracle import expected_flags, supported_claims
from bench.scenarios import Scenario


def ratio(num: int, den: int, empty: float | None = None) -> float | None:
    return empty if den == 0 else num / den


def score(scenario: Scenario, result: Result) -> dict[str, float | None]:
    claims = set(scenario.claims)
    before = supported_claims(scenario, set())
    after = supported_claims(scenario, scenario.truth_bad)
    falls = before - after
    survives = before & after
    held = claims - result.withdrawn
    truth = expected_flags(scenario)
    wrong = {did for did, label in truth.items() if label == "CORRECTION"}
    return {
        "leakage": ratio(len(held & falls), len(falls)),
        "preserved": ratio(len(held & survives), len(survives)),
        "precision": ratio(len(result.withdrawn & falls), len(result.withdrawn), empty=1.0),
        "missed": ratio(len(wrong - set(result.flagged)), len(wrong)),
        "labelled": ratio(
            sum(1 for did, label in truth.items() if result.flagged.get(did) == label),
            len(truth),
        ),
    }


def aggregate(rows: list[dict]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for key in rows[0]:
        values = [row[key] for row in rows if row[key] is not None]
        out[key] = sum(values) / len(values) if values else None
    return out
