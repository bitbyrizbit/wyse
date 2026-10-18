# Queries and Algorithms

Everything the product depends on, in the form it runs. Parameters are written `$name`. Every graph is one tenant or one agent scratch scope, so no query filters on tenant.

## Schema

One range index per label on `id`, then constraints that need it:

```cypher
CREATE INDEX FOR (n:Claim) ON (n.id)
```

```
GRAPH.CONSTRAINT CREATE <graph> UNIQUE NODE <Label> PROPERTIES 1 id
GRAPH.CONSTRAINT CREATE <graph> MANDATORY NODE <Label> PROPERTIES 1 tenant
```

Extra indexes cover `Claim.belief_status`, `Claim.use_status`, `Source.incident_state`, and `Decision.decided_at`. Constraints build asynchronously and are polled with `CALL db.constraints() YIELD status RETURN status` until all are OPERATIONAL.

## Writing evidence

An observation and its source:

```cypher
MERGE (s:Source {id: $sid})
  ON CREATE SET s.tenant = $tenant, s.kind = $kind, s.name = $name,
                s.trust_tier = $tier, s.incident_state = 'CLEAR'
MERGE (o:Observation {id: $oid})
  ON CREATE SET o.tenant = $tenant, o.content = $content, o.content_hash = $hash,
                o.observed_at = $observed, o.recorded_at = $now
MERGE (s)-[:CAPTURED_AS]->(o)
```

A justification, with its claim and all of its premises in one atomic query:

```cypher
MERGE (c:Claim {id: $cid})
  ON CREATE SET c.tenant = $tenant, c.subject = $subject, c.predicate = $predicate,
                c.object = $object, c.created_at = $now, c.revision = 1,
                c.belief_status = 'UNSUPPORTED', c.use_status = 'ELIGIBLE'
MERGE (j:Justification {id: $jid})
  ON CREATE SET j.tenant = $tenant, j.rule = $rule, j.state = 'INVALID'
MERGE (j)-[:JUSTIFIES]->(c)
WITH j
MATCH (p) WHERE p.id IN $premises
MERGE (j)-[:REQUIRES]->(p)
RETURN count(p) AS linked
```

Claim, justification, and source ids are hashes of their content, so the same proposition is the same node everywhere and repeated writes change nothing.

## Contradictions

```cypher
MATCH (o:Claim {subject: $s, predicate: $p})
WHERE o.object <> $o AND o.id <> $cid
RETURN o.id AS id
```

```cypher
UNWIND $pairs AS p
MATCH (a:Claim {id: p.a}), (b:Claim {id: p.b})
MERGE (a)-[:CONTRADICTS]->(b)
```

## Loading the belief graph

Each query below runs with `ORDER BY ... SKIP ... LIMIT` appended and is paged below half the server result cap.

```cypher
MATCH (c:Claim) RETURN c.id AS id, c.belief_status AS status, c.subject AS subject,
  c.predicate AS predicate, c.object AS object, c.use_status AS use, c.revision AS revision

MATCH (s:Source)-[:CAPTURED_AS]->(o:Observation)
RETURN o.id AS id, s.id AS source, s.incident_state AS state, s.trust_tier AS tier

MATCH (:Incident)-[:INVALIDATED]->(x) RETURN DISTINCT x.id AS id

MATCH (j:Justification)-[:JUSTIFIES]->(c:Claim) OPTIONAL MATCH (j)-[:REQUIRES]->(p)
RETURN j.id AS id, j.state AS state, c.id AS claim, collect(p.id) AS premises

MATCH (a:Claim)-[:CONTRADICTS]->(b:Claim) RETURN a.id AS a, b.id AS b

MATCH (d:Decision) OPTIONAL MATCH (d)-[:USED]->(c:Claim)
RETURN d.id AS id, d.summary AS summary, d.decided_at AS decided_at, d.acted AS acted,
  d.remediation AS remediation, d.snapshot AS snapshot, collect(c.id) AS claims
```

## Persisting beliefs: compare-and-set

A writer changes a claim only if it still holds the status the writer read. A stale writer fails the guard, reloads, and retries.

```cypher
UNWIND $rows AS r
MATCH (c:Claim {id: r.id}) WHERE c.belief_status = r.old
SET c.belief_status = r.status, c.revision = c.revision + 1
RETURN count(c) AS n
```

```cypher
UNWIND $rows AS r
MATCH (j:Justification {id: r.id}) WHERE j.state = r.old
SET j.state = r.state RETURN count(j) AS n
```

## Incidents

Each is a single atomic safety write that creates the incident.

```cypher
MATCH (s:Source {id: $sid})
SET s.incident_state = 'QUARANTINED'
CREATE (i:Incident {id: $iid, tenant: $tenant, kind: 'QUARANTINE', reason: $reason,
                    created_at: $now, result: '', target: $sid})
RETURN i.id AS id
```

```cypher
MATCH (c:Claim {id: $id}) WHERE c.belief_status <> 'RETRACTED'
SET c.belief_status = 'RETRACTED', c.revision = c.revision + 1
CREATE (i:Incident {id: $iid, tenant: $tenant, kind: 'RETRACTION', reason: $reason,
                    created_at: $now, result: '', target: $id})
CREATE (i)-[:INVALIDATED]->(c)
RETURN i.id AS id
```

Retracting an observation is the same shape with `MATCH (o:Observation {id: $id})`.

## Blast radius: graph traversal

Dependencies alternate direction, since a premise is reached through REQUIRES and a claim through JUSTIFIES, so impact discovery walks one level per query and stops on repeats and at a depth bound.

```cypher
MATCH (:Source {id: $id})-[:CAPTURED_AS]->(:Observation)<-[:REQUIRES]-
      (:Justification)-[:JUSTIFIES]->(c:Claim)
RETURN DISTINCT c.id AS id
```

```cypher
UNWIND $ids AS cid
MATCH (:Claim {id: cid})<-[:REQUIRES]-(:Justification)-[:JUSTIFIES]->(d:Claim)
RETURN DISTINCT d.id AS id
```

```cypher
MATCH (d:Decision)-[:USED]->(c:Claim) WHERE c.id IN $ids RETURN DISTINCT d.id AS id
```

The traversal reports `truncated` when it hits the depth bound or the result cap. A partial radius is never presented as complete.

## Decisions, promotion, handoffs

```cypher
MERGE (a:Agent {id: $aid}) ON CREATE SET a.tenant = $tenant, a.role = 'agent', a.scope = 'private'
CREATE (d:Decision {id: $did, tenant: $tenant, summary: $summary, decided_at: $now,
                    policy_version: $policy, remediation: 'NO_ACTION_REQUIRED',
                    acted: $acted, snapshot: $snapshot})
CREATE (a)-[:MADE]->(d)
WITH d
UNWIND $claims AS cid
MATCH (c:Claim {id: cid})
CREATE (d)-[:USED]->(c)
RETURN count(c) AS used
```

Promotion copies a proof closure into the shared graph with the same MERGE-on-id shapes as above, then records it:

```cypher
MERGE (a:Agent {id: $aid}) ON CREATE SET a.tenant = $tenant, a.role = 'agent', a.scope = 'shared'
CREATE (p:Promotion {id: $pid, tenant: $tenant, agent: $aid, scope: $scope, at: $now, claims: $claims})
CREATE (a)-[:MADE]->(p)
WITH p
UNWIND $ids AS cid
MATCH (c:Claim {id: cid})
CREATE (p)-[:PROMOTED]->(c)
RETURN count(c) AS n
```

A handoff is an Agent-to-Agent edge carrying a Handoff node:

```cypher
MERGE (a:Agent {id: $sender}) ON CREATE SET a.tenant = $tenant, a.role = 'agent', a.scope = 'shared'
MERGE (b:Agent {id: $receiver}) ON CREATE SET b.tenant = $tenant, b.role = 'agent', b.scope = 'shared'
CREATE (h:Handoff {id: $hid, tenant: $tenant, sender: $sender, receiver: $receiver,
                   at: $now, note: $note, package: $package})
CREATE (a)-[:HANDED_OFF {handoff: $hid}]->(b)
RETURN h.id AS id
```

## Algorithms

**Support evaluation** (`wyse/belief/core.py`). Least fixed point from valid observations. Each justification counts its distinct premises. When a premise becomes true, every justification fed by it decrements. At zero the justification is valid, and its claim becomes true unless it is blocked. Justifications with no premises never fire. Loops cannot sustain themselves, since nothing grounds them.

**Root propagation** (`wyse/belief/independence.py`). Every grounded observation roots itself. Each valid justification pushes the union of its premises' roots to its claim. Iteration runs to a fixed point over finite, growing sets. Independence is the number of distinct sources among a claim's roots.

**Contradiction resolution** (`wyse/belief/contradiction.py`). Supported claims linked by CONTRADICTS form groups by union-find. A group has a winner only when one claim has a strictly higher rank, where rank is the pair of best source tier and independent source count. Otherwise every claim in the group is CONTESTED. Recency never decides.

**Use eligibility.** The fixed point runs a second time with quarantined, restricted, and retracted claims blocked. A claim is usable only if it is supported, is reached in that second pass, and is not contested.

**Impact.** Analyze the tenant before and after a hypothetical or real withdrawal, then compare. Fell means live before and dead after. Survived means lost at least one valid justification but still stands. Decisions are labelled by the remediation rules in `docs/GOVERNANCE.md`, and labels only move up in severity during incident runs.
