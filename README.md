# WYSE

**Remember why.**

Agent memory has a quiet flaw. It stores what an agent was told and forgets why it believed it. One poisoned page, one stale record, one confident hallucination, and the error is promoted to fact, copied into summaries, and acted on for as long as the memory lives.

WYSE is a memory governance and recovery engine for AI agents, built on FalkorDB. Every belief it holds carries its evidence, its justification, and its dependents. When evidence collapses, WYSE does not delete blindly and does not look away. It works out which beliefs still stand on independent ground, which ones fall, which decisions leaned on the fallen, and what deserves a second look.

Hackathon: Graph Hacks, Context for AI Agents. **Track entered: Agent Memory and Coordination.**

## The idea in four moves

1. **Prove.** Every claim traces back to the observations and sources behind it.
2. **Justify.** A claim can rest on alternative proofs, where any one is enough, or on joint premises, where all are required. WYSE tells the two apart.
3. **Retract.** Withdraw evidence and the engine recomputes what remains supported instead of wiping everything downstream.
4. **Recover.** Decisions that relied on fallen beliefs are found, labelled, and queued for reassessment. Nothing is reversed automatically.

## Does it work? Measured.

A seeded benchmark compromises three of twelve sources across 70-claim scenarios, and scores each system against an independent oracle. Means over 20 seeds:

| System | Poisoned claims still served | Valid claims preserved | Withdrawal precision | Bad decisions missed | Decisions labelled correctly |
|---|---|---|---|---|---|
| Plain memory | 60.0% | 100.0% | 100.0% | 100.0% | 0.0% |
| Delete-cascade | 0.0% | 53.2% | 33.3% | 0.0% | 46.3% |
| **WYSE** | **0.0%** | **100.0%** | **100.0%** | **0.0%** | **100.0%** |

When half the alternative proofs secretly mirror the compromised source, WYSE leaks 17.7% of poisoned claims where delete-cascade leaks none. We publish that failure alongside the win. Independence is only as real as the sources are. Full method, tables, and limits are in [docs/BENCHMARK.md](docs/BENCHMARK.md).

Three agents citing one compromised email are one source, not three. Vote counting reports 10 where the truth is 1, and WYSE reports 1.

## How FalkorDB carries the product

The graph is the data model, and the product runs on it:

- **Evidence topology.** Sources, observations, claims, justifications, decisions, and agents are nodes. REQUIRES, JUSTIFIES, CAPTURED_AS, USED, and CONTRADICTS are edges. AND and OR support is the shape of the graph, with a justification node requiring all of its premises and several justifications pointing at one claim.
- **Blast radius by traversal.** Impact discovery walks the dependency graph in Cypher, one level per query, and survives cycles.
- **One graph per tenant and per agent.** Tenant isolation and private agent scratch memory come from FalkorDB's multi-graph design, with no extra deployments. Promotion copies a proof closure between graphs.
- **Integrity in the database.** Unique and mandatory constraints, deterministic MERGE on content-hashed ids, atomic single-query writes, and compare-and-set updates guard every state change.
- **Measured behavior.** Rollback, concurrency, isolation, constraints, and result-cap behavior were measured on the pinned build, and the findings are in [docs/FALKORDB_NOTES.md](docs/FALKORDB_NOTES.md).

Support evaluation itself runs in the application over the connected graph it loads. The queries and algorithms are listed in [docs/QUERIES.md](docs/QUERIES.md).

## What it ships with

- Justification-aware belief engine with grounded fixed-point support evaluation
- A retrieval gateway that re-derives belief on every read and withholds claims without ever returning their text
- Source quarantine, claim and observation retraction, and impact preview
- Decision snapshots, replay of what was believed, and reassessment against the present
- Private agent scratch memory, a promotion gate with tier caps and conflict checks, and provenance-carrying handoffs
- An MCP server with 12 tools, where identity and trust tier are never arguments
- A reproducible benchmark and 82 tests

## Quick start

Requirements: Python 3.11 and Docker.

```powershell
git clone https://github.com/bitbyrizbit/wyse.git
cd wyse
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
docker compose up -d
pytest -q
```

On macOS or Linux, use `python3.11 -m venv .venv`, `source .venv/bin/activate`, and `cp .env.example .env`.

FalkorDB runs from a pinned image in `docker-compose.yml` (graph module 6.0.2). Everything is free and runs locally.

### Watch the demo

```powershell
python scripts/demo.py
```

A research agent reads a forged invoice page. A billing agent acts on it. The page is quarantined, and WYSE shows what fell, what survived on independent proof, which decisions need attention, and what each agent can still read.

### Reproduce the benchmark

```powershell
python -m bench.runner --seeds 20
```

### Use it from an agent

```powershell
python -m wyse.mcp_server
```

Set `WYSE_TENANT`, `WYSE_AGENT`, and `WYSE_ROLE` in `.env`. See [docs/MCP.md](docs/MCP.md) for tools and host configuration.

## Repository layout

```
wyse/
  belief/       core algorithm, independence, contradictions, ingestion, recompute
  governance/   gateway, quarantine, retraction, impact, blast radius, decisions, replay, audit
  agents/       scratch scopes, promotion gate, handoffs
  service.py    the agent-facing surface
  mcp_server.py MCP tools over stdio
bench/          scenario generator, oracle, baselines, metrics, runner
scripts/        demo, FalkorDB probes, MCP smoke test
tests/          82 tests
docs/           design and findings
```

## Documentation

| Document | Contents |
|---|---|
| [SCOPE.md](docs/SCOPE.md) | Problem, ideas eliminated, design commitments |
| [DATA_MODEL.md](docs/DATA_MODEL.md) | Graph data model |
| [QUERIES.md](docs/QUERIES.md) | Cypher queries and algorithms the product depends on |
| [BELIEF_ENGINE.md](docs/BELIEF_ENGINE.md) | Support, independence, contradictions |
| [GOVERNANCE.md](docs/GOVERNANCE.md) | Gateway, incidents, decisions |
| [MULTI_AGENT.md](docs/MULTI_AGENT.md) | Scopes, promotion, handoffs, concurrency |
| [MCP.md](docs/MCP.md) | Tools, identity, authority |
| [BENCHMARK.md](docs/BENCHMARK.md) | Method and results |
| [FALKORDB_NOTES.md](docs/FALKORDB_NOTES.md) | Measured database behavior |
| [COMPARISON.md](docs/COMPARISON.md) | Existing memory systems |

## Known limits

- Independence is only as real as the sources are. Undeclared mirrors defeat it, as the benchmark shows.
- Recall and impact analysis load the whole tenant, so very large tenants will cost more.
- An agent-declared source kind is a claim and not a proof. Promotion caps the tier.
- Replay covers decisions. General time travel is not implemented.

## AI assistance disclosure

AI coding assistants were used throughout this project for design review, drafting, and code suggestions. Every model, query, and design decision was reviewed, tested, and is owned by the author. The test suite, the independent benchmark oracle, and the measured database findings exist to verify the work, and the author can explain the graph model, the queries, and the architecture.

## A note on the name

WYSE is an independent project. It is unrelated to any other product, company, or repository that uses the same or a similar name.

## License

Apache License 2.0. See [LICENSE](LICENSE).