# WYSE

**Remember why.**

Agent memory has a quiet flaw. It stores what an agent was told and forgets why it believed it. One poisoned page, one stale record, one confident hallucination, and the error is promoted to fact, copied into summaries, and acted on for as long as the memory lives.

WYSE is a memory governance and recovery engine for AI agents. Every belief it holds carries its evidence, its justification, and its dependents. When evidence collapses, WYSE does not delete blindly and does not look away. It works out which beliefs still stand on independent ground, which ones fall, which decisions leaned on the fallen, and what deserves a second look.

## The idea in four moves

1. **Prove.** Every claim is traced back to the observations and sources behind it.
2. **Justify.** A claim can rest on alternative proofs (any one is enough) or joint premises (all are required). WYSE tells the two apart.
3. **Retract.** Withdraw evidence and the engine recomputes what remains supported instead of wiping everything downstream.
4. **Recover.** Decisions that relied on fallen beliefs are found, classified, and queued for reassessment. Nothing is reversed automatically.

## Why a graph

Blast radius, selective survival, independent corroboration, and decision replay are all path questions. Remove FalkorDB and the product stops working, which is the point.

## What it will ship with

- Justification-aware belief engine with grounded support evaluation
- A single retrieval gateway that enforces belief status and use status
- Source quarantine with an immediate safety block
- Impact preview and selective retraction
- Decision snapshots and as-of replay
- Private and shared agent memory with a promotion gate
- An MCP server for agents
- A reproducible benchmark against baseline memory designs

## Stack

Python 3.11, FalkorDB, FastAPI, MCP. Everything runs locally with Docker and costs nothing.

## Status

Scope locked. Design documents live in `docs/`. Implementation begins when Graph Hacks opens on October 15, 2026.

Track: Agent Memory and Coordination.

## AI assistance disclosure

AI coding assistants are used in this project for design review, drafting, and code suggestions. Every model, query, and design decision is reviewed, tested, and owned by the author.

## A note on the name

WYSE is an independent project. It is unrelated to any other product, company, or repository that uses the same or a similar name.

## License

Apache License 2.0. See [LICENSE](LICENSE).