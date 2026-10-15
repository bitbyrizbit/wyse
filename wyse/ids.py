import time
import uuid


def new_id(kind: str) -> str:
    return f"{kind}_{uuid.uuid4().hex[:16]}"


def now_ms() -> int:
    return time.time_ns() // 1_000_000
