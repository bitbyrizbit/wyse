import threading
import time

from redis.exceptions import ResponseError

from wyse.db import Store
from wyse.schema import wait_for_constraints

TENANT = "probe"
store = Store()


def section(title: str) -> None:
    print(f"\n== {title}")


def fresh() -> None:
    store.drop(TENANT)
    store.write(TENANT, "CREATE (:Seed)")


def show_config() -> None:
    section("0. server config")
    print(store.connection.execute_command("GRAPH.CONFIG", "GET", "*"))


def rollback() -> None:
    section("1. rollback on a failed write")
    try:
        store.write(TENANT, "CREATE (:Probe {id: 'atom1'}) WITH 1 AS x RETURN x / 0")
        print("query was accepted")
    except ResponseError as exc:
        print("error:", exc)
    rows = store.read(TENANT, "MATCH (p:Probe {id: 'atom1'}) RETURN count(p) AS c")
    print("nodes left behind:", rows[0]["c"])


def contention() -> None:
    section("2. concurrent writers")
    per_thread = 50
    errors: list[str] = []

    def atomic_worker():
        for _ in range(per_thread):
            try:
                store.write(TENANT, "MATCH (c:Counter {id: 'atomic'}) SET c.n = c.n + 1")
            except Exception as exc:
                errors.append(str(exc))

    def naive_worker():
        for _ in range(per_thread):
            try:
                n = store.read(TENANT, "MATCH (c:Counter {id: 'naive'}) RETURN c.n AS n")[0]["n"]
                store.write(TENANT, "MATCH (c:Counter {id: 'naive'}) SET c.n = $n", {"n": n + 1})
            except Exception as exc:
                errors.append(str(exc))

    for threads in (16, 40):
        for name, worker in (("atomic", atomic_worker), ("naive", naive_worker)):
            store.write(TENANT, "MERGE (c:Counter {id: $name}) SET c.n = 0", {"name": name})
            errors.clear()
            pool = [threading.Thread(target=worker) for _ in range(threads)]
            started = time.perf_counter()
            for t in pool:
                t.start()
            for t in pool:
                t.join()
            elapsed = time.perf_counter() - started
            final = store.read(TENANT, "MATCH (c:Counter {id: $name}) RETURN c.n AS n", {"name": name})[0]["n"]
            print(f"{name:6} threads={threads} expected={threads * per_thread} final={final} "
                  f"errors={len(errors)} seconds={elapsed:.2f}")
            for message in sorted(set(errors))[:2]:
                print("   sample error:", message)


def isolation() -> None:
    section("3. graph isolation")
    other = "probe_other"
    store.drop(other)
    store.write(other, "CREATE (:Seed)")
    store.write(TENANT, "CREATE (:Secret {id: 's1'})")
    seen = store.read(other, "MATCH (s:Secret) RETURN count(s) AS c")[0]["c"]
    print("secrets visible from the other graph:", seen)
    print("tenants:", store.list_tenants())
    store.drop(other)


def cycles() -> None:
    section("4. traversal on a cycle")
    store.write(TENANT, "UNWIND range(0, 4) AS i CREATE (:Ring {i: i})")
    store.write(
        TENANT,
        "UNWIND range(0, 4) AS i MATCH (a:Ring {i: i}), (b:Ring {i: (i + 1) % 5}) CREATE (a)-[:NEXT]->(b)",
    )
    for depth in (3, 5, 10):
        rows = store.read(
            TENANT,
            f"MATCH (a:Ring {{i: 0}})-[:NEXT*1..{depth}]->(b) RETURN count(*) AS paths, count(DISTINCT b) AS nodes",
        )
        print(f"depth {depth}:", rows[0])
    try:
        rows = store.read(TENANT, "MATCH (a:Ring {i: 0})-[:NEXT*]->(b) RETURN count(*) AS paths", timeout_ms=2000)
        print("unbounded:", rows[0])
    except ResponseError as exc:
        print("unbounded error:", exc)


def constraints() -> None:
    section("5. constraint behavior")
    name = store.graph_name(TENANT)
    store.write(TENANT, "CREATE INDEX FOR (u:Uniq) ON (u.id)")
    store.connection.execute_command("GRAPH.CONSTRAINT", "CREATE", name, "UNIQUE", "NODE", "Uniq", "PROPERTIES", "1", "id")
    store.connection.execute_command("GRAPH.CONSTRAINT", "CREATE", name, "MANDATORY", "NODE", "Uniq", "PROPERTIES", "1", "tenant")
    wait_for_constraints(store, TENANT)
    store.write(TENANT, "CREATE (:Uniq {id: 'u1', tenant: 't'})")
    attempts = (
        ("duplicate", "CREATE (:Uniq {id: 'u1', tenant: 't'})"),
        ("missing property", "CREATE (:Uniq {id: 'u2'})"),
    )
    for label, query in attempts:
        try:
            store.write(TENANT, query)
            print(label, "-> accepted")
        except ResponseError as exc:
            print(label, "-> rejected:", exc)


def scale() -> None:
    section("6. traversal at scale")
    size = 20000
    store.write(TENANT, "CREATE INDEX FOR (c:Chain) ON (c.i)")
    started = time.perf_counter()
    store.write(TENANT, f"UNWIND range(0, {size - 1}) AS i CREATE (:Chain {{i: i}})")
    store.write(
        TENANT,
        f"UNWIND range(0, {size - 2}) AS i MATCH (a:Chain {{i: i}}), (b:Chain {{i: i + 1}}) CREATE (a)-[:NEXT]->(b)",
    )
    print(f"built {size} nodes in {time.perf_counter() - started:.2f}s")
    for depth in (10, 100, 1000, 5000):
        started = time.perf_counter()
        try:
            rows = store.read(
                TENANT,
                f"MATCH (a:Chain {{i: 0}})-[:NEXT*1..{depth}]->(b) RETURN count(b) AS reached",
                timeout_ms=15000,
            )
            print(f"depth {depth}: reached={rows[0]['reached']} seconds={time.perf_counter() - started:.3f}")
        except ResponseError as exc:
            print(f"depth {depth}: {exc}")


if __name__ == "__main__":
    fresh()
    show_config()
    rollback()
    contention()
    isolation()
    cycles()
    constraints()
    scale()
    store.drop(TENANT)
