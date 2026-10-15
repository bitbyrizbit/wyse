import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    password: str | None
    graph_prefix: str
    query_timeout_ms: int


def load_settings() -> Settings:
    return Settings(
        host=os.getenv("FALKORDB_HOST", "localhost"),
        port=int(os.getenv("FALKORDB_PORT", "6379")),
        password=os.getenv("FALKORDB_PASSWORD") or None,
        graph_prefix=os.getenv("WYSE_GRAPH_PREFIX", "wyse"),
        query_timeout_ms=int(os.getenv("WYSE_QUERY_TIMEOUT_MS", "5000")),
    )