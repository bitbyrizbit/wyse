# Belief Engine

How WYSE decides what is earned.

## Rules

- A justification is valid only when every premise it requires holds. A justification with no premises is never valid.
- A claim is supported when at least one of its justifications is valid.
- Support is the least fixed point computed outward from valid observations. A set of claims that only justify each other stays unsupported.
- An observation is valid unless its source is quarantined, or an incident invalidated it or its source.
- A retracted claim is blocked from support, and everything that depends only on it starves.

## Identity

- A claim id is a hash of the normalized subject, predicate and object, so one proposition is one claim. Text is stored lowercased with collapsed whitespace.
- A justification id is a hash of its claim and its sorted premises, so repeating identical evidence is a no-op.
- A source id is a hash of its kind and name.
- Trust tiers come from the source kind on the server. Unknown kinds fall to the lowest tier.

## Independence

Every supported claim carries the set of root observations beneath it, taken across all of its valid justifications. Independence is the number of distinct sources among those roots, so three agents citing one origin count once.

## Contradictions

Exclusive claims that share a subject and predicate but differ in object are linked with CONTRADICTS. Among supported claims in a conflict, a winner is named only on an explicit margin: higher trust tier, or equal tier with strictly more independent sources. Otherwise every claim in the conflict is CONTESTED. Recency never decides.

## Statuses

Recompute assigns RETRACTED, CONTESTED, SUPPORTED or UNSUPPORTED, bumps the claim revision when a status changes, and updates justification states. Use status is untouched here and belongs to quarantine.

## Known limits

- CONTESTED does not propagate to claims derived from a contested claim. The retrieval gateway reports that dependency instead.
- STALE is reserved and not assigned yet.
- Recompute is full-tenant and reads in several queries, so it is not a snapshot. Concurrent writers are handled in the multi-agent phase.
- Loads refuse to proceed at the 10,000 row cap.
