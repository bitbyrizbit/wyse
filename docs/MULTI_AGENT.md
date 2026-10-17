# Multi-Agent Memory

## Scopes

A scratch scope is a separate graph named after the tenant and the agent, for example `acme_a_alice`. Every engine function works inside it unchanged. Scratch memory is invisible to the shared graph and to other agents until it is promoted.

## Promotion

Promotion copies a claim and its whole proof closure into the shared graph: sources, observations, supporting claims, and justifications. Ids are deterministic, so the same proposition is the same claim everywhere and the same source is the same source everywhere. That is what makes independence correct across scopes.

The gate checks four things:

- **Usable:** only claims the scratch scope would release can cross.
- **Tier cap:** promoted sources are capped at TOOL. An agent cannot export self-declared authority.
- **Conflict:** if shared memory holds a usable claim with the same subject and predicate but a different object, the incoming claim must have strictly higher standing, or it is held with the reason CONFLICT.
- **Atomic proofs:** each justification lands with all of its premises in one query, so an interrupted promotion can only under-support a claim and never over-support it.

Every promotion is recorded with its agent, scope and claims. Revoking one retracts the promoted claims in the shared graph. Revocation withdraws the claim itself even if other evidence still supports it.

Supporting claims travel with the promoted claim and follow the ordinary contradiction policy. The conflict gate applies to the claims named in the request.

## Handoffs

A handoff carries claims with their revisions, statuses, and root evidence, plus the ids and reasons of claims that were withheld. Withheld claims carry no text. The recipient is checked. Opening a handoff re-derives every claim and reports drift: status changes, evidence changes, or loss of eligibility since the handoff was sent.

## Concurrency

FalkorDB serializes writers to a graph, and one query is atomic. WYSE builds on that:

- Claim and justification identities are deterministic, so concurrent writers converge on the same nodes.
- Recompute writes are compare-and-set. A stale writer fails the guard, reloads, and retries.
- Observation operation ids make retried writes idempotent.
- After concurrent writers finish, stored statuses equal a fresh analysis. This is asserted by test.

## Known limits

- The source kind label supplied at ingestion decides the trust tier. Agent-facing interfaces must not expose it, and promotion caps it.
- Writes to a tenant graph serialize, so throughput is bounded by the database and not by the engine.
- Handoffs and promotion read the full tenant.
