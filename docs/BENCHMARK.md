# Benchmark

Run date: October 18, 2026. Reproduce with `python -m bench.runner --seeds 20`.

## Method

A seeded generator builds layered evidence graphs. Base claims have one to three alternative proofs from different sources. Derived claims need two or three parent claims jointly, sometimes with an alternative derivation. Decisions cite one to three claims, and about 40% are marked as acted on. Three of twelve sources are then compromised.

Ground truth comes from an oracle of about thirty lines of set logic over the generator's own structure. It never imports engine code. It decides which claims truly fall, which survive on an alternative proof, and which decisions need correction or review.

Each scenario has 70 claims and 20 decisions. Results are means over 20 seeds.

## Systems

| System | What it models |
|---|---|
| Plain memory | Facts with source attribution and no lineage on derived claims. A claim is withdrawn only when every direct source is gone |
| Delete-cascade | Full provenance. Deletes everything downstream of a compromised source and ignores alternative proofs. Every flagged decision is called a correction |
| WYSE | The real engine on FalkorDB |

The baselines are reference designs written for this benchmark. They are not the named products, and no claim here is about any specific product.

## Metrics

- **Poisoned claims still served:** of the claims that truly fell, the share still returned to agents. Lower is better.
- **Valid claims preserved:** of the claims that truly survive on alternative proof, the share still served. Higher is better.
- **Withdrawal precision:** of the claims withdrawn, the share that truly fell. Higher is better.
- **Bad decisions missed:** of the decisions that truly need correction, the share never flagged at all. Lower is better.
- **Decisions labelled correctly:** of the decisions that truly need attention, the share carrying the correct class, correction or review. Higher is better.

## Results

### Clean: every alternative proof is independent

| System | Poisoned claims still served | Valid claims preserved | Withdrawal precision | Bad decisions missed | Decisions labelled correctly |
|---|---|---|---|---|---|
| Plain memory | 60.0% | 100.0% | 100.0% | 100.0% | 0.0% |
| Delete-cascade | 0.0% | 53.2% | 33.3% | 0.0% | 46.3% |
| WYSE | 0.0% | 100.0% | 100.0% | 0.0% | 100.0% |

### Failure case: half the alternative proofs secretly mirror the compromised source

The systems are told about the primary source only. The mirror is compromised in truth but unknown to them.

| System | Poisoned claims still served | Valid claims preserved | Withdrawal precision | Bad decisions missed | Decisions labelled correctly |
|---|---|---|---|---|---|
| Plain memory | 66.7% | 100.0% | 100.0% | 100.0% | 0.0% |
| Delete-cascade | 0.0% | 61.6% | 42.8% | 0.0% | 56.3% |
| WYSE | 17.7% | 100.0% | 100.0% | 0.0% | 91.3% |

### Operational cost (WYSE only, baselines are in-memory)

| Operation | Mean latency |
|---|---|
| Quarantine one source, including recompute and impact analysis | 71 ms |
| Gateway recall over the whole tenant | 32 ms |

### Corroboration: independent sources reported

| Agents confirming | Shared origin | Truth | Vote counting | WYSE |
|---|---|---|---|---|
| 2 | yes | 1 | 2 | 1 |
| 2 | no | 2 | 2 | 2 |
| 5 | yes | 1 | 5 | 1 |
| 5 | no | 5 | 5 | 5 |
| 10 | yes | 1 | 10 | 1 |
| 10 | no | 10 | 10 | 10 |

## Reading the results

**Plain memory** handles direct alternatives correctly and fails on everything derived. It serves 60% of the claims that should have fallen, and it never flags a decision, so every bad decision stands.

**Delete-cascade** is safe and wasteful. Nothing poisoned survives, but only 53.2% of valid claims are kept. Only a third of what it deletes was actually wrong. Because every flagged decision is called a correction, its labels are right for fewer than half.

**WYSE**, in the clean condition, matches the oracle on every metric. It withdraws exactly what fell, keeps everything that survives on independent proof, and labels each decision as a correction or a review.

**The failure case is the honest boundary.** When two sources look independent but share an origin that WYSE has not been told about, it keeps serving 17.7% of the poisoned claims, where delete-cascade serves none. The cause is the independence assumption itself. WYSE still flagged every truly wrong decision, with zero missed, but labelled 8.7% of them as reviews where corrections were due. The remedy is to quarantine the mirror once it is discovered, which the impact preview makes cheap. A declared source relationship in the data model is future work and is not measured here.

**Corroboration:** vote counting reports ten confirmations where the truth is one. WYSE reports the truth in all six cases.

## What this does not show

- The scenarios are synthetic and come from our own generator. They test whether the engine does what its semantics say. They do not prove that those semantics describe every real deployment.
- The oracle shares the support semantics of the engine, with alternative proofs as OR and joint premises as AND. It verifies the implementation and cannot validate the model.
- Results are means over 20 seeds, without confidence intervals.
- Latency was measured at 70 claims per tenant. Recall and impact analysis load the whole tenant, so large tenants will cost more.
- Undetected compromise defeats every system here by definition, and an untracked external copy of a poisoned claim is outside the model.
