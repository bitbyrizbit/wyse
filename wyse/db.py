import re

from falkordb import FalkorDB
from redis.exceptions import ResponseError

from wyse.config import Settings, load_settings

TENANT_PATTERN = re.compile(r"[a-z0-9_]{1,40}")


class Store:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or load_settings()
        self._db = FalkorDB(
            host=self.settings.host,
            port=self.settings.port,
            password=self.settings.password,
        )
        self._cap = None

    @property
    def connection(self):
        return self._db.connection

    def graph_name(self, tenant: str) -> str:
        if not TENANT_PATTERN.fullmatch(tenant):
            raise ValueError(f"invalid tenant id: {tenant!r}")
        return f"{self.settings.graph_prefix}_{tenant}"

    def ping(self) -> bool:
        return bool(self.connection.ping())

    def result_cap(self) -> int:
        if self._cap is None:
            reply = self.connection.execute_command("GRAPH.CONFIG", "GET", "RESULTSET_SIZE")
            self._cap = int(reply[1])
        return self._cap

    def run(self, tenant, cypher, params=None, *, readonly=False, timeout_ms=None):
        graph = self._db.select_graph(self.graph_name(tenant))
        if readonly:
            timeout = timeout_ms or self.settings.query_timeout_ms
            result = graph.ro_query(cypher, params, timeout=timeout)
        else:
            result = graph.query(cypher, params)
        names = [column[1] for column in result.header]
        return [dict(zip(names, row)) for row in result.result_set]

    def read(self, tenant, cypher, params=None, timeout_ms=None):
        return self.run(tenant, cypher, params, readonly=True, timeout_ms=timeout_ms)

    def write(self, tenant, cypher, params=None):
        return self.run(tenant, cypher, params)

    def drop(self, tenant: str) -> None:
        try:
            self._db.select_graph(self.graph_name(tenant)).delete()
        except ResponseError:
            pass

    def list_tenants(self) -> list[str]:
        prefix = f"{self.settings.graph_prefix}_"
        names = [n.decode() if isinstance(n, bytes) else n for n in self._db.list_graphs()]
        return sorted(n[len(prefix):] for n in names if n.startswith(prefix))