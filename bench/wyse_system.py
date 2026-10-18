import time
import uuid

from bench.baselines import Result
from bench.scenarios import Scenario
from wyse.belief.ingest import assert_claim, record_observation
from wyse.belief.policy import source_id_for
from wyse.belief.support import recompute
from wyse.db import Store
from wyse.governance.decisions import record_decision
from wyse.governance.gateway import recall
from wyse.governance.quarantine import quarantine_source
from wyse.schema import ensure_schema, wait_for_constraints


class Wyse:
    name = "WYSE"

    def __init__(self, store: Store):
        self.store = store

    def load(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.tenant = f"bench_{uuid.uuid4().hex[:10]}"
        self.store.write(self.tenant, "CREATE (:Seed)")
        ensure_schema(self.store, self.tenant)
        wait_for_constraints(self.store, self.tenant)

        self.claims: dict[str, str] = {}
        for cid, proofs in scenario.claims.items():
            evidence = []
            for proof in proofs:
                if proof.source is not None:
                    seen = record_observation(
                        self.store, self.tenant, source_kind=scenario.sources[proof.source],
                        source_name=proof.source, content=f"{proof.source} reports {cid}",
                    )
                    evidence.append([seen.observation_id])
                else:
                    evidence.append([self.claims[parent] for parent in proof.parents])
            self.claims[cid] = assert_claim(
                self.store, self.tenant, subject=f"e{cid}", predicate="status", object="ok",
                evidence=evidence, exclusive=False, recompute_now=False,
            )
        recompute(self.store, self.tenant)

        self.decisions: dict[str, str] = {}
        for decision in scenario.decisions:
            self.decisions[decision.id] = record_decision(
                self.store, self.tenant, agent_id="bench", summary=f"decision {decision.id}",
                claim_ids=[self.claims[cid] for cid in decision.claims], acted=decision.acted,
            )
        served = {item["claim_id"] for item in recall(self.store, self.tenant).usable}
        if served != set(self.claims.values()):
            raise RuntimeError("scenario did not load cleanly")

    def compromise(self, reported: list[str]) -> Result:
        started = time.perf_counter()
        for name in reported:
            source_id = source_id_for(self.scenario.sources[name], name)
            try:
                quarantine_source(self.store, self.tenant, source_id, "benchmark compromise")
            except ValueError:
                continue
        seconds = time.perf_counter() - started

        checked = time.perf_counter()
        served = {item["claim_id"] for item in recall(self.store, self.tenant).usable}
        recall_seconds = time.perf_counter() - checked

        withdrawn = {cid for cid, engine_id in self.claims.items() if engine_id not in served}
        rows = self.store.read(
            self.tenant, "MATCH (d:Decision) RETURN d.id AS id, d.remediation AS label"
        )
        labels = {row["id"]: row["label"] for row in rows}
        flagged: dict[str, str] = {}
        for did, engine_id in self.decisions.items():
            label = labels[engine_id]
            if label in ("CORRECTION_REQUIRED", "COMPENSATING_ACTION_REQUIRED"):
                flagged[did] = "CORRECTION"
            elif label in ("REVIEW_REQUIRED", "UNRESOLVED"):
                flagged[did] = "REVIEW"
        return Result(withdrawn, flagged, seconds, recall_seconds)

    def close(self) -> None:
        self.store.drop(self.tenant)
