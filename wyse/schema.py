import time

from redis.exceptions import ResponseError

from wyse.db import Store
from wyse.models import ALL_NODES

EXTRA_INDEXES = (
    ("Claim", "belief_status"),
    ("Claim", "use_status"),
    ("Source", "incident_state"),
    ("Decision", "decided_at"),
)


def _create_index(store: Store, tenant: str, label: str, prop: str) -> None:
    try:
        store.write(tenant, f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
    except ResponseError as exc:
        if "already" not in str(exc).lower():
            raise


def _create_constraint(store: Store, tenant: str, kind: str, label: str, prop: str) -> None:
    try:
        store.connection.execute_command(
            "GRAPH.CONSTRAINT", "CREATE", store.graph_name(tenant),
            kind, "NODE", label, "PROPERTIES", "1", prop,
        )
    except ResponseError as exc:
        if "already" not in str(exc).lower():
            raise


def ensure_schema(store: Store, tenant: str) -> None:
    for node in ALL_NODES:
        _create_index(store, tenant, node.label, "id")
    for label, prop in EXTRA_INDEXES:
        _create_index(store, tenant, label, prop)
    for node in ALL_NODES:
        _create_constraint(store, tenant, "UNIQUE", node.label, "id")
        _create_constraint(store, tenant, "MANDATORY", node.label, "tenant")


def wait_for_constraints(store: Store, tenant: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    statuses: list[str] = []
    while time.monotonic() < deadline:
        rows = store.read(tenant, "CALL db.constraints() YIELD status RETURN status")
        statuses = [row["status"] for row in rows]
        if "FAILED" in statuses:
            raise RuntimeError("a constraint failed to build")
        if statuses and all(status == "OPERATIONAL" for status in statuses):
            return
        time.sleep(0.2)
    raise TimeoutError(f"constraints not operational, last statuses: {statuses}")
