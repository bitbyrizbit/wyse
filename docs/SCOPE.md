# WYSE

**Remember why.**

Project scope document. Graph Hacks: Context for AI Agents (FalkorDB x WeMakeDevs). Track 02: Agent Memory and Coordination. Solo entry.

Status: scope locked. This document holds ideas, design, and decisions only. No application code is written before the hackathon opens (Oct 15, 12:01 AM IST).

---

## 1. What WYSE is

WYSE is a memory governance and recovery engine for AI agents.

Most agent memory systems store what an agent was told and retrieve it later. WYSE stores something different: **why the agent believes what it believes**. Every belief carries its evidence, its justification, and its dependents. When evidence turns out to be wrong, fake, or hostile, WYSE does not delete blindly and does not let the damage stay hidden. It works out which beliefs still stand on independent ground, which ones fall, which decisions leaned on the fallen ones, and what needs reassessing.

One sentence: **memory that can prove what it knows, and take back what it should not.**

---

## 2. The problem

### 2.1 What the track describes

Agents see pieces, not the whole picture. They lose track of earlier sessions, miss how things relate, and cannot explain their choices.

### 2.2 The root cause we are going after

Most teams will read that as a storage problem: store more, retrieve better. We read it as a trust and causality problem.

**An agent cannot tell which of its beliefs to trust, and cannot undo a bad one.**

Concrete failure modes:

- A tool output or web page says something wrong or malicious. The agent stores it as fact. It survives into every later session. This is persistent memory poisoning, and published research on memory-poisoning attacks against agents already shows it works in practice.
- A bad fact gets summarized, combined with other facts, and acted on. Deleting the original leaves every child alive.
- Several agents confirm the same claim, but all of them read the same compromised source. Three votes, one root. Naive corroboration counts it as three.
- Two agents write conflicting facts at the same time and nothing principled decides the outcome.
- Nobody can answer: what did the agent believe when it made that decision, and what did that belief rest on?
- A belief can stay true while a decision made on bad evidence is still unacceptable. Systems that only track facts miss this.

### 2.3 The framing shift

Do not build a memory database. A database remembers what was written. A retrieval system finds what looks relevant. WYSE decides whether a memory is still justified, whether its justification changed, which conclusions survive, which past actions are now suspect, and what should happen next.

---

## 3. Existing solutions and where they stop

This comparison is based on what we know of public documentation. **All competitor claims must be re-verified against current docs before they appear in the README, the blog post, or the demo.** Never write "nobody does X" unless verified.

| System | What it does well | Where WYSE differs |
|---|---|---|
| Mem0 | Memory extraction, update, retrieval, graph relationships | Facts do not carry a justification structure or a dependency-aware recovery path |
| Zep / Graphiti | Temporal knowledge graph, source episodes, provenance, fact invalidation over time | Tracks when and where facts came from. Does not, as far as we know, evaluate whether a belief is still justified after evidence is withdrawn, or trace affected decisions |
| Letta (MemGPT) | Stateful agents, memory tiers, context management | Focus is context management, not trust, justification, or undo |
| Cognee, LangMem and similar | Pipelines that build memory and knowledge | Build memory, do not govern it. Needs feature-by-feature verification |

The shared gap: existing systems track time and sources. They do not track **causality and trust** across the full chain from evidence to belief to decision.

We do not claim to be the first to think about this. Truth-maintenance systems, data provenance, and database recovery have deep prior art. Our contribution is combining justification-aware belief maintenance, security-aware invalidation, and decision-level recovery in an agent memory system, then **measuring** whether the combination works.

---

## 4. Ideas we eliminated on purpose

These are what a thousand teams will build. We are not building them:

- A chatbot with long-term graph memory
- A personal second brain
- GraphRAG question answering over documents
- Shared memory for support agents with a graph visualizer
- Fraud investigation or security triage agents (Track 01 defaults)
- A generic company knowledge graph (Track 03 default)
- Anything where the graph is a nicer view of data that would work in Postgres

Test applied to every feature: if FalkorDB is removed, does the product stop working? If not, the feature does not belong.

---

## 5. The core idea: justification-aware belief maintenance

### 5.1 Beliefs have a chain

```
Source -> Observation -> Claim -> (derived Claim) -> Decision -> Action -> Outcome
```

Example: a web page says an invoice is paid. That is an observation about what the page says, not proof that payment settled. The system records the observation, proposes a claim, assesses it, and later a billing agent may decide something based on it.

### 5.2 Retraction is not deletion

If that web page turns out to be fraudulent, a naive system deletes the claim, overwrites it, or leaves it alive inside a summary. WYSE does this instead:

1. Preserve the historical record of what was observed and believed.
2. Mark the affected source or evidence as compromised or withdrawn.
3. Find every claim whose justification depends on that evidence.
4. Recompute whether each claim still has valid support.
5. Find decisions that used the affected claims.
6. Keep claims that have independent alternative support.
7. Flag decisions for review, correction, or simulated recovery.

Step 6 is the heart of it. If a payment-provider record independently confirms the payment, the claim survives even though the original page is now untrusted.

### 5.3 Support sets: AND and OR

A graph of plain "derived from" edges cannot tell these two situations apart:

- **Alternative support (OR):** the provider record OR a verified bank statement can each support "invoice settled".
- **Joint support (AND):** "customer has no outstanding balance" needs both "invoice settled" AND "no other open invoices".

So justification is a first-class node:

```
Claim C1: Invoice is settled
  Justification J1: premise = Observation O17 (provider settlement)   state = VALID
  Justification J2: premise = Observation O29 (bank statement match)  state = VALID
```

- Invalidate O17: J1 falls, C1 stays supported through J2.
- Invalidate O29 as well: C1 becomes unsupported.

A justification is valid only if all of its required premises are valid. A claim is supported if at least one of its justifications is valid.

### 5.4 Grounded evaluation and cycles

Support is computed outward from valid observations. A claim is only supported if a chain of valid justifications reaches grounded evidence. If A supports B and B supports A, neither survives on that loop alone, because nothing grounds it. Cyclic derivations are rejected or evaluated with a defined grounded rule. Circular reasoning must never keep a belief alive.

---

## 6. Design principles

1. No consequential belief without provenance.
2. No derived conclusion without a justification.
3. No silent conflict resolution.
4. No retraction without dependency analysis.
5. No consequential action without an auditable decision record.
6. The LLM may propose. The governance engine decides.
7. WYSE does not promise that every belief is true. It promises that the basis of a belief is explainable, uncertainty is visible, and the system responds systematically when that basis changes.

---

## 7. Data model

### 7.1 Nodes

| Node | Purpose |
|---|---|
| Source | Where information came from: a tool, page, user, another agent. Has a trust tier and incident status |
| Observation | What a source actually said at a time. Content hash, timestamp, captured content or reference |
| Claim | A normalized proposition the system may believe. Revision, belief status, use status |
| Justification | One way a claim can be supported. Required premises, rule, state |
| Entity | Things claims are about |
| Agent | Who observed, proposed, used, or promoted something, and in which scope |
| Decision | What an agent decided, with a snapshot of the claims and statuses it used |
| Incident | A recorded retraction or quarantine event with scope and results |

### 7.2 Edges

| Edge | Meaning |
|---|---|
| CAPTURED_AS | Source to Observation |
| SUPPORTS | Observation or Claim to Justification (as premise evidence) |
| REQUIRES | Justification to each required premise |
| JUSTIFIES | Justification to Claim |
| ABOUT | Claim to Entity |
| CONTRADICTS | Claim to Claim |
| SUPERSEDES | New claim revision to earlier revision |
| USED | Decision to the Claim revisions it relied on |
| INVALIDATED_BY | Evidence or claim to an Incident |
| HANDED_OFF | Handoff record to the context it carried |

### 7.3 Two separate status fields

A single `is_valid` flag is too blunt. Epistemic status and security eligibility are different questions, so they live in separate fields.

**Belief status** (is it justified?):

- SUPPORTED: at least one acceptable justification holds
- UNSUPPORTED: no acceptable justification remains
- CONTESTED: material conflict exists
- STALE: freshness condition expired
- RETRACTED: explicitly withdrawn

**Use status** (may it be used?):

- ELIGIBLE
- QUARANTINED: blocked by a security incident, even if well supported
- RESTRICTED: not allowed for the intended use

A claim can be well supported and still not usable. A claim can be usable and still contested. The retrieval gate returns both, so the agent sees the full picture.

### 7.4 Trust is several dimensions, not one score

- Origin assurance: can we establish where it came from
- Evidence quality: does the source actually support the proposition
- Corroboration: is there genuinely independent support
- Freshness: is it timely enough for the task
- Policy eligibility: is it allowed for this use

No single numeric trust score. A score hides which dimension is the problem.

---

## 8. Mechanisms

### 8.1 Governed ingestion

Every write passes through one pipeline:

1. Identify the caller, agent, and tenant.
2. Validate and size-limit the payload.
3. Capture the observation with source, timestamp, and content hash.
4. Let the LLM propose candidate claims. Proposed claims are not verified truth.
5. Apply deterministic policy: source tier, corroboration requirements, contradictions.
6. Commit claim, justification, evidence links, and initial status.
7. Return a receipt with identifiers and the outcome.

Trust labels are assigned by the server. An agent can never write its own trust label.

### 8.2 Independence by evidence ancestry

Corroboration counts independent roots, not votes. Three agents repeating one compromised email are one source. For every claim, trace its evidence ancestry and detect shared upstream observations. Independence rules start conservative and explainable. We do not claim mathematical independence in the general case.

### 8.3 Contradiction handling on write

New conflicting claims never overwrite old ones. They are linked with CONTRADICTS or SUPERSEDES, and an explicit policy (trust tier, recency, independent corroboration) decides which is preferred. The loser stays in history.

### 8.4 The retrieval gateway

Quarantine means nothing if bad memory can leak out through another path. Every recall passes through one gateway that enforces:

- Tenant and agent authorization
- Current belief status and use status
- Source quarantine
- Freshness requirements
- Conflict visibility
- Provenance and uncertainty

It returns a structured evidence package, not a bare list of strings. Quarantined information must never become usable because a different retrieval path finds it.

### 8.5 Retraction and quarantine

Two phases, kept separate on purpose:

- **Immediate safety:** the moment a quarantine or retraction is accepted, affected evidence is blocked at the gateway.
- **Recomputation:** a worker traverses dependents, re-evaluates justifications, updates statuses, and finds affected decisions.

Security response must not wait for a large traversal to finish.

`inspect_impact` previews a retraction before running it: what would fall, what would survive on independent support, which decisions are touched. A preview is not a guarantee, since new writes can land before execution, so the real run recomputes.

Impact discovery sketch (illustrative, not the final production query):

```cypher
MATCH (target:Claim {id: $claim_id})
MATCH (affected:Claim)-[:DERIVED_FROM*1..]->(target)
OPTIONAL MATCH (d:Decision)-[:USED]->(affected)
RETURN affected.id AS affected_claim, collect(DISTINCT d.id) AS affected_decisions
```

The production path goes through Justification nodes, evaluates alternative support, handles cycles and duplicate paths, bounds traversal depth, and reports truncation explicitly. A partial traversal must never be presented as a complete blast radius.

Output of a retraction (all reported, none silently dropped):

- Directly invalidated
- Became unsupported
- Still supported by independent evidence
- Contested or pending
- Decisions affected
- Whether recovery is complete

### 8.6 Decisions, replay, and impact

Every decision stores a snapshot: the claim revisions it used, their statuses at the time, the evidence references, and the policy in force.

Two different questions, never conflated:

- **Historical replay (as_of):** what did the agent know at decision time? Reconstruct the recorded context faithfully, without silently substituting corrected evidence.
- **Current reassessment:** given what we know now, how should that decision be judged?

This reconstructs the recorded decision context. It does not promise deterministic regeneration of an LLM answer, since models and tools can change.

Affected decisions get a remediation class:

| Class | Meaning |
|---|---|
| NO_ACTION_REQUIRED | Outcome still valid under current policy |
| REVIEW_REQUIRED | A human or authorized agent should reassess |
| CORRECTION_REQUIRED | Outcome is no longer justified |
| COMPENSATING_ACTION_REQUIRED | A consequential action happened and recovery may be needed |
| UNRESOLVED | Evidence is insufficient to decide |

Key insight: **a belief can stay correct while a decision's evidentiary basis becomes unacceptable.** That is why decisions are tracked separately from claims.

Remediation is simulated with approval gates. WYSE never refunds, notifies, or reverses anything on its own. There is a designed path to authorized real execution later.

### 8.7 Multi-agent memory

- Each agent writes to a private scratch scope first.
- Claims move into shared memory through a promotion gate that checks authorization, evidence quality, contradictions, and independence.
- Visibility is not trust: a claim can be visible to a team without being approved for consequential use.
- Promote evidence-backed claims, not just agent-written summaries. Summaries stay linked to their support and can be invalidated.
- Handoffs carry a provenance-preserving context package: claims, revisions, evidence references, statuses, unresolved conflicts.
- Promotion is reversible. A promoted claim stays linked to its origin and promotion decision.
- Tenants get isolated graphs through FalkorDB's multi-graph design. Tenant isolation and agent isolation are different requirements, so scope authorization is enforced in the application on every read and write regardless of topology. Exact FalkorDB behavior is verified before relying on it.

### 8.8 Concurrency

Optimistic revision checks on claims. Writes carry an expected revision and an operation ID. A stale revision does not discard incoming evidence: it is evaluated as a correction, a contradiction, or a superseding version. Retract operations are idempotent. We do not assume a read followed by a graph write is atomic. Atomicity guarantees are tested against the chosen FalkorDB version, and where they are missing we add per-claim coordination.

### 8.9 Retract versus erase

Epistemic retraction ("this claim is no longer justified") and privacy erasure ("delete this data") are different operations. Retraction keeps a record that the claim existed and why it was withdrawn. Erasure must remove content, including derived copies. WYSE implements retraction. Erasure is documented as designed future work, with the honest note that after erasure the original reasoning may no longer be fully reconstructable.

---

## 9. Agent interface (MCP)

WYSE is exposed to agents as an MCP server. The engine stays usable without MCP.

| Tool | Responsibility |
|---|---|
| remember | Submit evidence or a candidate claim for governed ingestion |
| recall | Retrieve authorized memory with provenance and both statuses |
| explain_belief | Show why a claim is supported, contested, or unsupported |
| inspect_impact | Preview what a retraction or quarantine would affect |
| retract | Withdraw a claim and run recovery |
| quarantine | Block use of a compromised source or evidence scope |
| reassess | Re-evaluate a past decision against current evidence |
| as_of | Reconstruct the recorded memory state at a past time |
| handoff | Transfer a provenance-preserving context package |
| promote | Request promotion from private to shared scope |

Write APIs are idempotent with stable operation IDs and versioned contracts.

---

## 10. Why the graph is load-bearing

FalkorDB does the work that makes WYSE what it is:

- Multi-hop provenance traversal from evidence to claims to decisions
- Justification and dependency traversal for support evaluation
- Impact discovery across claims, decisions, and handoffs
- Shared-ancestry detection for independence checks
- Per-tenant isolated graphs
- Reconstructing the dependency network around a past decision

Remove FalkorDB and blast radius, selective survival, independence, and replay all stop working. That satisfies the hackathon rule that the graph must do real work and not decorate ordinary storage.

---

## 11. Evaluation: proof, not vibes

Every headline claim maps to a measurable result. The benchmark is reproducible and runs without a paid API.

### 11.1 Scenario environment (synthetic data)

- Multiple tenants and agent roles with handoffs
- Benign evidence and deliberately poisoned sources
- Independent and correlated sources
- Derived claims with single and alternative justifications
- Contradictory evidence
- Concurrent writes and retractions
- Decisions that lead to simulated actions
- Ground truth kept separate from the system under test, so it can never leak in as an input. Fixed seeds and a holdout set not used for tuning

### 11.2 Baselines

1. Plain persistent memory: store and retrieve, no dependency recovery
2. Delete-cascade memory: provenance links, cascade deletes descendants
3. Provenance-only memory: tracks lineage, no justification evaluation
4. WYSE: provenance, justifications, quarantine, decision impact

Baselines isolate which component creates which improvement. A real third-party baseline is used only if feasible and is labeled honestly. Otherwise we implement our own baselines and say so.

### 11.3 Metrics

- Downstream contamination rate after recovery (lower is better)
- Retraction precision and recall, published together so high recall cannot hide over-invalidation
- Independent-support preservation: how often valid claims survive when alternative support exists
- Time to safe retrieval: from quarantine accepted to the gateway reliably blocking affected evidence
- Replay fidelity: recorded evidence, revisions, and policy actually reconstructed, with mismatches reported
- Concurrency correctness: lost updates, duplicate operations, invalid intermediate reads, final-state consistency
- Operational cost: ingestion, retrieval, and retraction latency

A system that refuses to retrieve anything would look safe. The benchmark must show WYSE reduces poisoned influence while preserving legitimate knowledge.

### 11.4 Published failure cases

We publish where WYSE fails:

- Two sources secretly share an upstream origin
- A poisoned claim copied into an untracked external summary
- A decision whose input context was never recorded
- A compromise that is never detected
- An alternative justification wrongly classified as independent
- A traversal truncated by limits
- A write racing a retraction

These define the real limits and make the results credible.

---

## 12. Demo story

A research agent reads a poisoned page. A billing agent later makes a decision on the resulting claim. A second, independent record supports part of the same conclusion.

On screen:

1. Before: the chain from source to claim to decision.
2. The source is flagged. Immediate quarantine: the poisoned evidence disappears from recall.
3. Impact preview, then retraction. Claims with independent support survive. Claims without it fall.
4. The billing decision is marked affected even though the underlying fact survived, with its remediation class.
5. as_of replay shows exactly what the agent knew at decision time.
6. The benchmark table against the baselines, including a failure case.

The interface answers four questions: what happened, what was affected, which decisions might be wrong, what is fixed and what still needs attention. The graph view explains the system. It is not the only way to understand it.

---

## 13. Technology stack (all free)

| Layer | Choice |
|---|---|
| Graph database | FalkorDB, run locally with Docker (primary database, required) |
| Backend | Python, FastAPI, typed domain models, deterministic policy and support evaluation |
| Agent interface | MCP server |
| Models | Provider-independent adapter. Free-tier API or local model for extraction and explanation. The engine never depends on one LLM. Free limits verified before committing |
| Retrieval | Graph traversal and indexed text first. A small local embedding layer only if recall demands it. No separate vector database initially |
| Frontend | Incident-centered web UI with belief explorer, incident timeline, decision replay, benchmark report. Framework chosen at build time |
| Testing | Unit and property-based tests, graph integration tests, deterministic synthetic scenarios, failure injection |
| Hosting | FalkorDB Cloud free tier or similar if limits allow. Complete local Docker setup instructions as the accepted fallback |

The stack is not bound to anything used in earlier projects. Choose what serves the engine best, as long as everything stays free.

---

## 14. Scope tiers

Not tied to days or a schedule. Ordered by importance and dependency. Build the correctness model before the spectacle.

### Tier 1: the engine (the project is not complete without these)

- Domain model: Source, Observation, Claim, Justification, Decision, Agent, Incident
- Support evaluation with AND/OR justifications, grounded evaluation, cycle safety
- Governed ingestion with server-controlled trust
- Contradiction handling without overwrite
- Retrieval gateway with belief status and use status
- Quarantine with immediate safety block
- Retract with inspect_impact and selective recovery
- Independence by evidence ancestry
- Decision snapshots, as_of replay, impact classification, simulated remediation
- Benchmark with baselines, metrics, and published failure cases
- MCP server exposing the core tools

### Tier 2: multi-agent

- Private scratch scope and promotion gate
- Provenance-preserving handoffs
- Tenant isolation through multiple graphs
- Concurrency tests and a published correctness result

### Tier 3: experience and depth

- Incident console and decision replay UI
- Belief explorer
- Counterfactual fragility analysis: which beliefs a decision is most dependent on, and which rest on a single weak source
- Reusable benchmark packaging

Tier 1 first, and finished properly. Each later tier is added only when the earlier one is solid.

---

## 15. What we will not build

- An LLM that decides whether another LLM is trustworthy. Models may supply signals. Integrity rules are deterministic.
- A single universal trust score
- Automatic LLM re-derivation of every descendant
- A blockchain or any immutable ledger
- Autonomous remediation with real-world side effects
- A UI where the graph visualization is the whole product
- Unsupported guarantees: never "poisoning-proof", never "perfect replay", never "compliance-certified"
- Microservices, event buses, or workflow frameworks before there is a reason

---

## 16. Hackathon requirements checklist

Everything the rules mark as required must be satisfied.

- [ ] FalkorDB is the primary graph database and supports a central part of the product
- [ ] The graph does real work (product breaks without it)
- [ ] Public source-code repository
- [ ] README with setup instructions and the graph data model
- [ ] The Cypher queries or graph algorithms the product depends on documented
- [ ] Demo video showing the working project
- [ ] Live deployment, or complete local setup instructions
- [ ] Track named at submission (Track 02: Agent Memory and Coordination)
- [ ] AI coding assistant use disclosed
- [ ] Author can explain the graph model, queries, architecture, and technical decisions
- [ ] Meaningful human contribution, verification, and understanding (not an unreviewed AI dump)
- [ ] Main coding and design work starts after Oct 15, 12:01 AM IST. Before that: notes, graph model sketches, diagrams only
- [ ] Only public, synthetic, or own data. No private, login-protected, paywalled, or personal data
- [ ] Submission before Oct 18, 11:59 PM IST
- [ ] Blog post written (side prize, best blog post)

---

## 17. Verification before building

Settle these by checking, not guessing:

1. Current Zep, Graphiti, Mem0, Letta, Cognee docs for the comparison table
2. Cited research (memory-poisoning papers and benchmarks): confirm they exist and what they say before citing
3. FalkorDB: atomicity within one query, transaction and isolation behavior, multi-graph capabilities, exact version, and free cloud limits
4. Whether a small real third-party baseline is feasible
5. Naming conflicts for "WYSE" (the name is also used by an older commercial hardware brand, so the README should make the project's identity unmistakable and avoid implying any link)
6. Official Track 02 brief and judging criteria, since the official page is the authority over this document

---

## 18. Honest positioning

What WYSE claims:

- It evaluates whether a belief is still justified after evidence is withdrawn, preserving beliefs that have independent support.
- It traces compromised evidence into derived beliefs, decisions, and affected actions.
- It reconstructs the recorded context behind a decision.
- It governs how claims move between private and shared memory.
- It measures all of the above against baselines, and publishes where it fails.

What WYSE does not claim:

- That it makes memory poisoning impossible
- That every stored belief is true
- That it is the first system to think about provenance or truth maintenance
- Perfect or deterministic replay of model behavior

The central research question: **can an agent memory system recover from invalid evidence while preserving everything that remains independently justified, and show which decisions need reassessment?**

Everything else supports that question.

---

## 19. Why this matters

Agents are being given persistent memory and the authority to act. Memory that cannot explain itself or be corrected turns one bad input into a permanent, spreading error. The industry is adding memory faster than it is adding the means to audit and repair it.

The goal is not only to win a hackathon. It is to redefine what agent memory should be: not a store of things remembered, but a body of evidence with reasons attached.

Remember why.