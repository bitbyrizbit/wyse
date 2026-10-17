# FalkorDB Findings

Measured on the pinned build with `scripts/probe_falkordb.py`, `scripts/probe_limits.py`, and the test suite.

## Environment

| Item | Value |
|---|---|
| FalkorDB graph module | 6.0.2 |
| Redis | 8.10.2 |
| Image digest | sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6 |
| Docker Desktop | 4.95.0 |
| TIMEOUT | 1000 (TIMEOUT_DEFAULT 0, TIMEOUT_MAX 0) |
| RESULTSET_SIZE | 10000 |
| MAX_QUEUED_QUERIES | 25 |
| THREAD_COUNT | 16 |

## Questions

1. **Does a failed write leave anything behind?**
   No. A query that created a node and then failed with a division by zero left zero nodes. A multi-node create that violated a unique constraint also left nothing behind.

2. **What happens under concurrent writers?**
   A single-query increment is exact: 800 of 800 at 16 threads, 2000 of 2000 at 40 threads, about 4000 writes per second. A read followed by a write retained 90 of 800 and 112 of 2000 updates, with no errors raised. Lost updates are silent. MAX_QUEUED_QUERIES was not reached at 40 threads.

3. **Are tenant graphs invisible to each other?**
   Yes. Data created in one graph returned zero rows from another.

4. **How does variable-length traversal behave on cycles?**
   A five-node ring returned 3, 5, and 5 paths at depths 3, 5, and 10. The unbounded form terminated with 5. Edges are used once per path, and results count paths, so node counts need DISTINCT.

5. **How are constraints enforced?**
   Unique and mandatory constraints both reject violating writes with clear messages: "unique constraint violation on node of type Uniq" and "mandatory constraint violation: node with label Uniq missing property tenant". Creation is asynchronous and reaches OPERATIONAL.

6. **How do deep traversals perform at 20,000 nodes?**
   On a linear chain: depth 10 in 2 ms, depth 1000 in 2 ms, depth 5000 in 9 ms. Building the graph took 1.55 s. Branching graphs are not yet measured.

7. **What happens at the result cap and at the timeout?**
   A query matching 20,000 nodes returned exactly 10,000 rows with no error and no warning, so truncation at the result cap is silent. A cross join given a 500 ms per-query timeout was aborted after 0.50 s with a ResponseError reading "Query timed out". Write queries are sent without a timeout.

## Consequences for the design

- Revision checks are compare-and-set inside a single query. Read-modify-write is banned everywhere in the engine.
- One query is the unit of atomicity. Multi-query operations record progress and must be safe to rerun.
- Every traversal result is deduplicated with DISTINCT.
- Bulk loads page with ORDER BY, SKIP and LIMIT, sized from the configured result cap, so no read ever lands on the cap.
- The benchmark must include wide, branching dependency graphs, not only chains.
