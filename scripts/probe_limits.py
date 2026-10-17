import time

from redis.exceptions import ResponseError

from wyse.db import Store

TENANT = "limits"
store = Store()

store.drop(TENANT)
store.write(TENANT, "CREATE (:Seed)")
store.write(TENANT, "UNWIND range(0, 19999) AS i CREATE (:Chain {i: i})")

rows = store.read(TENANT, "MATCH (c:Chain) RETURN c.i AS i", timeout_ms=30000)
print("rows returned for 20000 matches:", len(rows))

started = time.perf_counter()
try:
    store.read(TENANT, "MATCH (a:Chain), (b:Chain) RETURN count(*) AS n", timeout_ms=500)
    print("slow query finished without a timeout")
except ResponseError as exc:
    print("slow query error:", exc)
print(f"elapsed {time.perf_counter() - started:.2f}s")

store.drop(TENANT)
