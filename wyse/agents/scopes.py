import re

from wyse.db import Store
from wyse.schema import ensure_schema, wait_for_constraints

AGENT_PATTERN = re.compile(r"[a-z0-9]{1,16}")


def scratch_scope(tenant: str, agent: str) -> str:
    if not AGENT_PATTERN.fullmatch(agent):
        raise ValueError(f"invalid agent id: {agent!r}")
    if "_a_" in tenant:
        raise ValueError("tenant ids may not contain the scratch marker")
    return f"{tenant}_a_{agent}"


def open_scratch(store: Store, tenant: str, agent: str) -> str:
    scope = scratch_scope(tenant, agent)
    store.graph_name(scope)
    ensure_schema(store, scope)
    wait_for_constraints(store, scope)
    return scope
