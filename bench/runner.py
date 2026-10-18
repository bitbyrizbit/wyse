import argparse
import uuid
from pathlib import Path

from bench.baselines import Cascade, Plain
from bench.metrics import aggregate, score
from bench.report import render_independence, render_latency, render_table
from bench.scenarios import generate
from bench.wyse_system import Wyse
from wyse.belief.ingest import assert_claim, record_observation
from wyse.belief.support import analyze, load_state
from wyse.db import Store
from wyse.schema import ensure_schema, wait_for_constraints

CONDITIONS = (
    ("Clean: every alternative proof is independent", 0.0),
    ("Failure case: half the alternative proofs secretly mirror the compromised source", 0.5),
)


def run_condition(store: Store, mirror_rate: float, seeds: int, params: dict):
    systems = [Plain(), Cascade(), Wyse(store)]
    rows: dict[str, list[dict]] = {system.name: [] for system in systems}
    latencies: list[dict] = []
    for seed in range(seeds):
        scenario = generate(seed, mirror_rate=mirror_rate, **params)
        for system in systems:
            system.load(scenario)
            try:
                result = system.compromise(scenario.reported)
            finally:
                system.close()
            rows[system.name].append(score(scenario, result))
            if system.name == "WYSE":
                latencies.append(
                    {
                        "quarantine_ms": result.seconds * 1000 / len(scenario.reported),
                        "recall_ms": result.recall_seconds * 1000,
                    }
                )
        print(f"seed {seed + 1}/{seeds} done", flush=True)
    return {name: aggregate(data) for name, data in rows.items()}, latencies


def independence(store: Store) -> list[dict]:
    rows = []
    for agents in (2, 5, 10):
        for correlated in (True, False):
            tenant = f"bench_ind_{uuid.uuid4().hex[:8]}"
            store.write(tenant, "CREATE (:Seed)")
            ensure_schema(store, tenant)
            wait_for_constraints(store, tenant)
            try:
                shared = record_observation(
                    store, tenant, source_kind="tool", source_name="origin",
                    content="bank details changed",
                )
                checks = []
                for i in range(agents):
                    seen = shared if correlated else record_observation(
                        store, tenant, source_kind="tool", source_name=f"origin{i}",
                        content=f"agent {i} saw the change",
                    )
                    checks.append(
                        assert_claim(
                            store, tenant, subject=f"agent{i}", predicate="verified",
                            object="bank change", evidence=[[seen.observation_id]],
                            exclusive=False, recompute_now=False,
                        )
                    )
                final = assert_claim(
                    store, tenant, subject="supplier", predicate="bank", object="changed",
                    evidence=[[check] for check in checks], exclusive=False,
                )
                analysis = analyze(load_state(store, tenant))
                rows.append(
                    {
                        "agents": agents,
                        "correlated": correlated,
                        "truth": 1 if correlated else agents,
                        "votes": agents,
                        "wyse": len(analysis.independent_sources[final]),
                    }
                )
            finally:
                store.drop(tenant)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--base", type=int, default=40)
    parser.add_argument("--derived", type=int, default=30)
    parser.add_argument("--decisions", type=int, default=20)
    args = parser.parse_args()

    store = Store()
    params = {"n_base": args.base, "n_derived": args.derived, "n_decisions": args.decisions}
    parts = [
        f"Seeds: {args.seeds}. Claims per scenario: {args.base + args.derived}. "
        f"Decisions per scenario: {args.decisions}. Compromised sources: 3 of 12."
    ]
    latencies: list[dict] = []
    for title, rate in CONDITIONS:
        table, latency = run_condition(store, rate, args.seeds, params)
        parts.append(render_table(title, table))
        latencies += latency
    parts.append(render_latency(latencies))
    parts.append(render_independence(independence(store)))

    text = "\n\n".join(parts)
    print("\n" + text)
    out = Path("bench/results")
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
