# WYSE Data Model

The authoritative description of what lives in the graph. Where this file and SCOPE.md differ, this file wins. Specifically, premise links are expressed with `REQUIRES` alone, and derived claims are expressed through justifications whose premises are other claims.

Every node carries a `tenant` property. Every tenant owns its own graph.

## Nodes

| Node | Purpose | Key properties |
|---|---|---|
| Source | Where information came from: a tool, a web page, a user, an agent | id, kind, name, trust_tier, incident_state |
| Observation | What a source actually said, at a moment in time | id, content, content_hash, observed_at, recorded_at |
| Claim | A normalized proposition the system may believe | id, subject, predicate, object, revision, belief_status, use_status, created_at |
| Justification | One way a claim can be supported | id, rule, state |
| Entity | A thing that claims are about | id, name, kind |
| Agent | Who observed, proposed, decided, or promoted | id, role, scope |
| Decision | What an agent decided, with its evidence frozen at that instant | id, summary, decided_at, policy_version, remediation |
| Incident | A recorded retraction or quarantine event | id, kind, reason, created_at, result |

## Edges

| Edge | From | To | Meaning |
|---|---|---|---|
| CAPTURED_AS | Source | Observation | The source produced this observation |
| REQUIRES | Justification | Observation or Claim | A premise this justification depends on |
| JUSTIFIES | Justification | Claim | The claim this justification supports |
| ABOUT | Claim | Entity | The claim concerns this entity |
| CONTRADICTS | Claim | Claim | The two claims cannot both hold |
| SUPERSEDES | Claim | Claim | A newer revision replaces an older one |
| PROPOSED | Agent | Claim | The agent put this claim forward |
| MADE | Agent | Decision | The agent took this decision |
| USED | Decision | Claim | The decision relied on this claim revision |
| INVALIDATED | Incident | Source, Observation, or Claim | The incident withdrew this item |
| HANDED_OFF | Agent | Agent | Context transferred, with the claims included as a property |

## Support rules

- A justification is VALID only when every premise it REQUIRES is valid.
- A claim is SUPPORTED when at least one justification that JUSTIFIES it is VALID.
- An observation is valid unless its source is quarantined or an incident invalidated it.
- Support is evaluated outward from valid observations. A set of claims that justify each other with no grounded observation beneath them is UNSUPPORTED.

## Two status fields

Belief status answers whether a claim is justified.

| Value | Meaning |
|---|---|
| SUPPORTED | At least one valid justification exists |
| UNSUPPORTED | No valid justification remains |
| CONTESTED | A conflicting claim is also in play |
| STALE | A freshness condition has expired |
| RETRACTED | Explicitly withdrawn |

Use status answers whether a claim may be used.

| Value | Meaning |
|---|---|
| ELIGIBLE | Available to readers |
| QUARANTINED | Blocked by an incident, regardless of support |
| RESTRICTED | Not permitted for the requested purpose |

A claim can be SUPPORTED and QUARANTINED at once. The retrieval gateway reports both fields on every read.

## Source trust tiers

| Tier | Example |
|---|---|
| USER | A verified instruction from the user |
| SYSTEM | A first-party record inside the deployment |
| TOOL | Output from a registered tool |
| AGENT | An inference made by an agent |
| WEB | Content from the open web |

Tiers are assigned by the server. No caller can set its own tier.

## Remediation classes for decisions

| Class | Meaning |
|---|---|
| NO_ACTION_REQUIRED | The outcome still holds under current evidence |
| REVIEW_REQUIRED | A human or authorized agent should reassess |
| CORRECTION_REQUIRED | The outcome is no longer justified |
| COMPENSATING_ACTION_REQUIRED | A consequential action happened and recovery may be needed |
| UNRESOLVED | The evidence cannot settle the question |

## Invariants

1. Nothing is overwritten. New conflicting claims are linked, and older revisions remain in history.
2. A claim without a justification is never SUPPORTED.
3. Trust tiers are server-assigned.
4. Every decision records the claim revisions it used.
5. Retraction changes how information is treated. It never erases the evidence that an incident occurred.
6. A traversal that hit its depth limit reports itself as partial.


## Traversal and atomicity notes

- Dependency flow alternates direction. A premise is reached from a justification through REQUIRES, and a claim is reached from the same justification through JUSTIFIES, so impact discovery cannot be a single variable-length pattern. It runs as an application-driven walk, one level per query, which also produces depth bounds and truncation flags.
- Identity-bearing nodes are created with separate MERGE clauses, followed by a MERGE on the relationship. Merging a whole path can duplicate endpoints.
- Constraints are created through GRAPH.CONSTRAINT CREATE over an exact-match index, complete asynchronously, and are verified before the engine relies on them.
- One modifying query is atomic, writers to a single graph are serialized, and readers see a consistent snapshot. Revision checks are compare-and-set operations inside one query. Retraction progress is stored on the Incident node, so it updates atomically without a second store.
- Each behavior above is verified on the pinned server version before it is relied on.

## Governance additions

- Source `incident_state` is CLEAR or QUARANTINED. A quarantined source stops grounding beliefs the moment the flag flips.
- Incident carries a `target` property naming what it acted on and a `result` property holding the recorded impact as JSON. Retractions also link to their target through INVALIDATED.
- Decision carries `acted`, which marks a consequential action, and `snapshot`, a JSON record of the claim revisions, statuses and root evidence at decision time.

## Implementation status

Implemented: the nodes Source, Observation, Claim, Justification, Decision, Agent, Incident, Promotion, and Handoff, and the edges CAPTURED_AS, REQUIRES, JUSTIFIES, CONTRADICTS, USED, MADE, PROPOSED, INVALIDATED, PROMOTED, and HANDED_OFF.

Reserved and not yet used: the Entity node, the ABOUT and SUPERSEDES edges, and the STALE belief status.
