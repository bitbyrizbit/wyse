# FalkorDB Findings

Measured on the pinned build. Every claim below was produced by `scripts/probe_falkordb.py` or the test suite.

## Environment

| Item | Value |
|---|---|
| FalkorDB graph module | 6.0.2 (module ver 60002) |
| Redis | 8.10.2 |
| Image digest | sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6 |
| Host OS | Linux 6.6.87.2-microsoft-standard-WSL2 x86_64 (inside Docker Desktop) |
| Defaults observed | TIMEOUT 1000 ms, RESULTSET_SIZE 10000, MAX_QUEUED_QUERIES 25, THREAD_COUNT 16, CACHE_SIZE 25 |

## Questions

1. **Does a failed write leave anything behind?**

   Result: **No — writes are atomic and roll back completely on error.**
   A `CREATE (:Probe {id: 'atom1'}) WITH 1 AS x RETURN x / 0` raised `Division by zero`
   and left zero nodes behind (`nodes left behind: 0`). Confirmed independently by
   `test_failed_query_leaves_nothing_behind`: a single statement that tries to create two
   nodes with the same id is rejected and the graph is unchanged.

2. **What happens under concurrent writers, atomic versus read-then-write?**

   Result: **Atomic (single-query) writes serialise correctly; naïve read-modify-write loses
   the vast majority of updates with no errors raised.**

   | Strategy | Threads | Expected | Final | Errors |
   |---|---|---|---|---|
   | atomic SET in one query | 16 | 800 | 800 | 0 |
   | naïve read-then-write   | 16 | 800 | 90  | 0 |
   | atomic SET in one query | 40 | 2000 | 2000 | 0 |
   | naïve read-then-write   | 40 | 2000 | 112  | 0 |

   The naïve pattern silently discards ~95 % of increments because FalkorDB does not raise
   a conflict error — the last writer wins. Any counter or balance that must be exact must
   be updated in a single Cypher statement that reads and writes in one round trip.

3. **Are tenant graphs invisible to each other?**

   Result: **Yes — complete isolation.** A `:Secret` node written to `probe` was queried
   from `probe_other` and returned `count = 0`. Graphs share the same server but have
   entirely separate keyspaces. `store.list_tenants()` correctly enumerated both graphs by
   prefix without cross-contamination.

4. **How does variable-length traversal behave on cycles and unbounded depth?**

   Result: **Bounded traversal caps correctly; unbounded traversal on a 5-node cycle
   returns immediately without hanging.**

   A ring of 5 nodes connected `[:NEXT]` in a cycle:

   | Depth bound | paths | distinct nodes |
   |---|---|---|
   | `*1..3` | 3 | 3 |
   | `*1..5` | 5 | 5 |
   | `*1..10` | 5 | 5 (cycle capped at unique nodes) |
   | `*` (unbounded) | 5 | — (returned immediately) |

   FalkorDB does not loop infinitely on an unbounded traversal over a cycle; it visits each
   node at most once and returns. The server-level TIMEOUT (1000 ms) is a backstop but was
   not needed here.

5. **How are unique and mandatory constraints enforced, and what does a violation look like?**

   Result: **Both constraint types are enforced at write time with clear, specific error
   messages. Violations raise `redis.exceptions.ResponseError`.**

   - Duplicate unique value: `unique constraint violation on node of type Uniq`
   - Missing mandatory property: `mandatory constraint violation: node with label Uniq missing property tenant`

   Constraints build asynchronously after `GRAPH.CONSTRAINT CREATE`. The `wait_for_constraints`
   helper polls `CALL db.constraints() YIELD status` and raises `TimeoutError` if any
   constraint stays non-OPERATIONAL past the deadline, and `RuntimeError` if any reaches
   FAILED. Schema setup is idempotent: re-running `ensure_schema` on an existing graph is
   safe (`already` responses are swallowed).

6. **How do deep traversals perform on 20,000 nodes, and where do limits bite?**

   Result: **Linear-chain traversal is extremely fast up to depth 5000. The default
   RESULTSET_SIZE of 10,000 is the first limit to hit in practice, not traversal time.**

   | Depth | Nodes reached | Time |
   |---|---|---|
   | 10 | 10 | 0.002 s |
   | 100 | 100 | 0.001 s |
   | 1000 | 1000 | 0.002 s |
   | 5000 | 5000 | 0.009 s |

   Building 20,000 nodes and 19,999 edges took 1.55 s. Depth 5000 traversal (returning
   a count, not raw rows) ran in 9 ms. Queries that return raw rows instead of aggregates
   will hit RESULTSET_SIZE = 10,000 before depth becomes a concern.

## Consequences for the design

- **Never use read-then-write for any value that must be exact** (counters, revision
  numbers, balance fields). All such mutations must be expressed as a single Cypher
  statement that atomically reads and sets the value in one round trip.

- **The `Claim.revision` bump must be a single `SET c.revision = c.revision + 1`** inside
  the same query that updates `belief_status` or `use_status`. A separate read before the
  write will silently lose increments under concurrency.

- **Tenant isolation is reliable** and enforced by graph-name separation, not by any
  application-layer filter. Validating tenant ids against `TENANT_PATTERN` before forming
  the graph name is the only guard needed.

- **Constraint errors surface as `ResponseError`** with a human-readable message. Callers
  should catch `ResponseError` and inspect the message to distinguish a duplicate-id
  violation from a missing-property violation.

- **`wait_for_constraints` is required after schema creation** before the first write that
  depends on a constraint. The default 15-second timeout is generous; on this hardware
  constraints became OPERATIONAL in well under 1 second.

- **RESULTSET_SIZE = 10,000** is the practical row limit for `MATCH` queries that return
  raw nodes. Queries used for governance (belief propagation, incident scanning) must use
  aggregation (`count`, `collect`) or pagination rather than returning unbounded node lists.

- **Unbounded `[*]` traversal on a cycle does not hang**, but it should still be avoided in
  production Cypher because the behaviour is undocumented and the TIMEOUT backstop (1000 ms
  by default) is the only safety net if the graph topology changes.
