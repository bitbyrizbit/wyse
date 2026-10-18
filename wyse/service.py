from dataclasses import asdict

from wyse.agents.handoff import handoff as send_handoff
from wyse.agents.handoff import open_handoff as read_handoff
from wyse.agents.promotion import promote as promote_claims
from wyse.agents.scopes import scratch_scope
from wyse.belief.ingest import remember as store_fact
from wyse.db import Store
from wyse.governance.asof import reassess as reassess_decision
from wyse.governance.asof import recorded_context
from wyse.governance.audit import explain_belief as explain
from wyse.governance.blast import blast_radius
from wyse.governance.decisions import record_decision as store_decision
from wyse.governance.gateway import recall as read_memory
from wyse.governance.impact import inspect_impact as preview_impact
from wyse.governance.quarantine import quarantine_source
from wyse.governance.retract import retract_claim
from wyse.schema import ensure_schema, wait_for_constraints

AGENT_KINDS = {"agent", "tool", "web"}
OPERATOR_KINDS = AGENT_KINDS | {"system", "user"}
ROLES = {"agent", "operator"}


class Service:
    def __init__(self, store: Store, tenant: str, agent: str, role: str = "agent"):
        if role not in ROLES:
            raise ValueError(f"role must be one of {sorted(ROLES)}")
        store.graph_name(tenant)
        scratch_scope(tenant, agent)
        self.store = store
        self.tenant = tenant
        self.agent = agent
        self.role = role
        self._ready: set[str] = set()

    @property
    def prepared(self) -> set[str]:
        return set(self._ready)

    def _prepare(self, name: str) -> None:
        if name in self._ready:
            return
        self.store.write(name, "MERGE (:Seed {id: 'seed'})")
        ensure_schema(self.store, name)
        wait_for_constraints(self.store, name)
        self._ready.add(name)

    def _resolve(self, scope: str, write: bool = False) -> str:
        if scope == "shared":
            name = self.tenant
            if write and self.role != "operator":
                raise PermissionError("only operators may change shared memory directly")
        elif scope == "private":
            name = scratch_scope(self.tenant, self.agent)
        else:
            raise ValueError("scope must be 'shared' or 'private'")
        self._prepare(name)
        return name

    def remember(
        self, source_name: str, content: str, subject: str, predicate: str, object: str,
        source_kind: str = "agent", scope: str = "private", operation_id: str | None = None,
    ) -> dict:
        allowed = OPERATOR_KINDS if self.role == "operator" else AGENT_KINDS
        kind = source_kind.strip().lower()
        if kind not in allowed:
            raise ValueError(f"source_kind must be one of {sorted(allowed)}")
        name = self._resolve(scope, write=True)
        saved = store_fact(
            self.store, name, source_kind=kind, source_name=source_name, content=content,
            subject=subject, predicate=predicate, object=object,
            agent_id=self.agent, operation_id=operation_id,
        )
        return {
            "claim_id": saved.claim_id,
            "observation_id": saved.observation_id,
            "source_id": saved.source_id,
        }

    def recall(
        self, subject: str | None = None, predicate: str | None = None, scope: str = "shared",
    ) -> dict:
        name = self._resolve(scope)
        return asdict(read_memory(self.store, name, subject=subject, predicate=predicate))

    def explain_belief(self, claim_id: str, scope: str = "shared") -> dict:
        return explain(self.store, self._resolve(scope), claim_id)

    def inspect_impact(
        self, source_id: str | None = None, observation_id: str | None = None,
        claim_id: str | None = None, scope: str = "shared",
    ) -> dict:
        name = self._resolve(scope)
        impact = preview_impact(
            self.store, name,
            source_id=source_id, observation_id=observation_id, claim_id=claim_id,
        )
        out = impact.as_dict()
        out["blast_radius"] = blast_radius(
            self.store, name,
            source_id=source_id, observation_id=observation_id, claim_id=claim_id,
        )
        return out

    def retract(self, claim_id: str, reason: str, scope: str = "private") -> dict:
        incident_id, impact = retract_claim(
            self.store, self._resolve(scope, write=True), claim_id, reason
        )
        return {"incident_id": incident_id, "impact": impact.as_dict()}

    def quarantine(self, source_id: str, reason: str, scope: str = "private") -> dict:
        incident_id, impact = quarantine_source(
            self.store, self._resolve(scope, write=True), source_id, reason
        )
        return {"incident_id": incident_id, "impact": impact.as_dict()}

    def record_decision(
        self, summary: str, claim_ids: list[str], acted: bool = False, scope: str = "shared",
    ) -> str:
        return store_decision(
            self.store, self._resolve(scope), agent_id=self.agent,
            summary=summary, claim_ids=claim_ids, acted=acted,
        )

    def reassess(self, decision_id: str, scope: str = "shared") -> dict:
        return reassess_decision(self.store, self._resolve(scope), decision_id)

    def as_of(self, decision_id: str, scope: str = "shared") -> dict:
        return recorded_context(self.store, self._resolve(scope), decision_id)

    def promote(self, claim_ids: list[str]) -> dict:
        self._resolve("private")
        self._resolve("shared")
        return asdict(promote_claims(self.store, self.tenant, self.agent, claim_ids))

    def handoff(self, receiver: str, claim_ids: list[str], note: str = "") -> str:
        return send_handoff(
            self.store, self._resolve("shared"), self.agent, receiver, claim_ids, note
        )

    def open_handoff(self, handoff_id: str) -> dict:
        return read_handoff(self.store, self._resolve("shared"), handoff_id, self.agent)
