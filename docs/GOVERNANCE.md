# Governance

How WYSE controls what agents may use and recovers when evidence dies.

## The retrieval gateway

Every recall re-derives belief and use eligibility from ground truth. Stored statuses are treated as a cache and never trusted at read time. A quarantine takes effect on the next recall, before any recompute has run.

A recall returns three groups. Usable claims are supported and eligible. Contested claims are returned with their conflicts so the agent can weigh them. Withheld claims carry only an id, a status, and a reason, and never their text.

Use eligibility is computed separately from support. A claim stays eligible if some proof reaches it without passing through a quarantined or restricted claim.

## Incidents

Quarantining a source, retracting an observation, and retracting a claim all follow one sequence:

1. Load and analyze the current state.
2. Apply a single atomic safety write that creates the incident.
3. Recompute beliefs, guarded by compare-and-set on claim status.
4. Diff the before and after analyses.
5. Label affected decisions and log the result on the incident.

`inspect_impact` runs the same diff against a hypothetical state without writing anything. A preview is not a guarantee, since new writes can land first. The real run recomputes.

## Impact vocabulary

- **fell**: live before, unsupported or retracted after
- **survived**: lost a justification but still stands on another
- **changed**: every claim whose status moved

## Decisions

A decision may only cite claims the gateway would release. It freezes the claim revisions, statuses and root evidence at that instant. `recorded_context` returns that frozen record. `reassess` compares it with the present. The two are never blended.

| Situation | Label |
|---|---|
| Used a claim that fell | CORRECTION_REQUIRED, or COMPENSATING_ACTION_REQUIRED if an action was taken |
| Claim survived but its evidence lost a proof or went contested | REVIEW_REQUIRED |
| Affected, but no snapshot to verify | UNRESOLVED |
| Not affected | NO_ACTION_REQUIRED |

Labels are advice. WYSE reverses nothing on its own.

## Known limits

- Recall and impact analysis load the full tenant. That is correct and simple at this scale, and incremental analysis is future work.
- The gap between a decision check and its write is small but not zero. A quarantine landing inside it is caught by the next reassessment.
- There is no general time travel. Replay covers decisions, which record what the agent saw.
- Source release after a false alarm is not implemented.
