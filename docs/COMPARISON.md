# Comparison with existing memory systems

Source: public documentation reviewed on October 13, 2026. "Not documented" means the pages reviewed did not describe the capability. It does not mean the capability is absent. Cognee and Graphiti entries marked "verify" need a deeper pass through source and API docs before any claim is published.

| Dimension | Zep / Graphiti | Mem0 | Letta | Cognee | WYSE |
|---|---|---|---|---|---|
| Source lineage | Yes. Source episodes are retained and linked to derived facts | Partial. Identifiers and metadata, no claim-to-source graph | Partial. Metadata and timestamps | Verify | Core. Every claim traces to observations and sources |
| Temporal validity | Yes. Facts carry valid and invalid times | Partial. Optional expiry | Timestamps only | Partial. Temporal retrieval mode | Claim revisions plus decision-time snapshots |
| Retraction semantics | Deleting an episode does not revert an invalidation, and derived edges can remain if other episodes support them | Explicit update and delete, no documented downstream recalculation | Edit or delete blocks and passages. Deleting a shared block removes it from every attached agent | Delete data items or datasets, downstream cleanup to verify | Selective retraction with support recomputation |
| Dependency-aware recalculation (AND and OR support) | Not documented | Not documented | Not documented | Not documented | Core |
| Decision records | Not documented as a first-class object | Decisions stored as memories, not evidence-linked records | Not a core primitive | None identified | Core. Decisions freeze the claim revisions they used |
| As-of replay | Fact history yes. Decision-context replay not documented | Not documented | Not documented | Not documented | Core |
| Multi-agent promotion | Namespaces through group IDs, no promotion gate documented | Scopes for user, agent, app and run | Shared blocks, concurrent updates can be last-write-wins | Dataset scope and permissions | Private scope, promotion gate, provenance-carrying handoffs |
| Quarantine | Not documented | Not documented | Not documented | Not documented | Immediate gateway block while impact analysis runs |

Zep states plainly that provenance does not prove truth. WYSE shares that premise and builds on it: provenance records where a belief came from, and justification evaluation decides whether it is still earned.

Mem0 graph memory is a Platform feature, and the open-source tier differs. Any comparison must name the tier.

WYSE entries describe design goals. They become claims only when the benchmark supports them.