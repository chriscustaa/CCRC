# CCRC Trajectory100 Final Audit Certificate v1

Date: 2026-08-28 UTC  
Experiment: `ccrc-trajectory100-qwen35-9b-q4km-v1`

## Verdict

**Computational integrity: PASS. Scientific disposition: INCONCLUSIVE. Do not advance the frozen five-stage trajectory rule to a fresh 300-item test.**

The experiment demonstrates substantial response movement and recoverability, but the preregistered truth-blind selector did not separate repairs from harms reliably enough to qualify.

## Source artifact

`experiment_trajectory100_final.zip`  
SHA-256: `064b309d642d826888ddcb870a0ada8005176257a49d917ad183b2cf477a2a94`

## Integrity reconstruction

- ZIP decompression: PASS
- All packaged file hashes: PASS
- Frozen inputs match the trusted v0.9.0 package byte-for-byte: PASS
- Frozen internal hashes: PASS
- Independent harness validation: PASS, zero errors
- Planned/completed base cells: 500/500
- Actual model calls: 502, including two frozen format retries
- Exact model ID on all cells: `qwen/qwen3.5-9b`
- Exact runtime snapshot on all cells: `d8ec616a61e2046592391ff4739e6e53048d9027a0669d24b1f6b1ca9567568b`
- Responses endpoint: 500/500
- Explicit seeds accepted: 500/500
- Reasoning telemetry detected: 0
- Stateful continuation or prior-answer leakage: 0
- Median cell latency: 2.599 seconds
- Independent reconstruction of prompt hashes, candidate gaps, correctness, control offsets, and policy decisions: PASS

## Frozen primary result

Primary cohort: all 60 unique pre-confirmatory `g < 0.20` items.

Frozen rule: switch away from T0 only when T2=T3=T4 agree on a different answer and the median control-centered T2:T4 gap change is positive.

| Metric | Result | Frozen requirement |
|---|---:|---:|
| Switches | 11 | — |
| Repairs | 5 | ≥5 |
| Harms | 4 | — |
| Net | **+1** | ≥+3 |
| Harm/repair ratio | **0.80** | ≤0.50 |
| One-sided exact p | 0.500 | Descriptive |

The rule meets only the minimum-repair count. It fails the net and safety-ratio gates; therefore the frozen disposition is **INCONCLUSIVE**.

Across all 100 items, the rule produced 5 repairs and 5 harms: net zero.

## What the trajectory revealed

Among the 60 low-gap items:

- Fresh T0: 18 correct, 42 wrong.
- Twenty-one of the 42 T0 errors became correct at least once later: **50% oracle recoverability**.
- Sixteen of the 18 correct T0 answers became wrong at least once: **89% fragility exposure**.
- Fifty of 60 items changed answers at least once.
- Thirty-three of 60 changed answers at least twice.

This supports the original distinction: low confidence contains both recoverable errors and correct-but-fragile answers. It also shows why intervention alone is insufficient—the recoverability and damage channels are both large.

## Confidence did not track correctness cleanly across interventions

The four depth prompts globally increased gap magnitude relative to T0. Median control offsets were:

- T1: +0.1083
- T2: +0.2893
- T3: +0.2886
- T4: +0.1174

Yet whole-sample accuracy moved from 51% at T0 to 49%, 49%, 46%, and 51% at T1–T4. On the low-gap core, mean gap rose roughly fourfold by T3 while accuracy moved only from 30.0% to 31.7%.

Inference: stronger deliberation wording can increase expressed confidence without increasing correctness. Cross-template raw gap slopes must not be interpreted as literal belief improvement. The control-centering safeguard was necessary, but it did not yield a safe selector.

## Exploratory direct-stage results

These comparisons were not the frozen primary endpoint and cannot be promoted without independent validation.

| Direct substitution on low-gap core | Repairs | Harms | Net | One-sided exact p |
|---|---:|---:|---:|---:|
| T1 | 15 | 8 | +7 | 0.105 |
| T2 | 14 | 8 | +6 | 0.143 |
| T3 | 13 | 12 | +1 | 0.500 |
| T4 | 12 | 7 | +5 | 0.180 |

T1 is the strongest exploratory candidate, but it does not replicate across the two source cohorts:

- consensus600 core: 9 repairs / 2 harms, net +7
- fresh-only I5 core: 6 repairs / 6 harms, net 0

The frozen trajectory rule has the same instability:

- consensus600 core: 3 repairs / 0 harms, net +3
- fresh-only I5 core: 2 repairs / 4 harms, net −2

Therefore no T1 or trajectory efficacy claim is warranted from this pilot.

## Decision and next test

1. Retire the frozen five-stage switching rule; do not run its proposed fresh 300-item expansion.
2. Do not fit or tune a new trajectory classifier on these 100 outcomes.
3. Preserve T1 only as a new bridge hypothesis because it is simpler, cheaper, and directionally positive—but source-unstable.

If one final lightweight operational test is desired, use the 326 disjoint low-gap items already identified in the completed 7,818-item sample:

- Run exactly one new stateless T1 call per item.
- Keep the prior frozen B0 outcome as comparator.
- Use all 326 items; no truth-based inclusion or exclusion.
- Freeze the existing T1 wording, model/runtime, option order, and parser.
- Primary endpoint: exact paired repairs versus harms.
- Advance only if one-sided p < 0.05, net > 0, and harms/repairs ≤ 0.50.
- Otherwise retire prompt-based correction and move to the separately designed full-logit sycophancy mechanism test.

Expected workload: 326 new calls, approximately 15–25 minutes locally, $0.

## State Vector

- **Anchor:** Gap remains a strong triage sensor; neither verifier consensus nor five-stage trajectory selection has demonstrated safe correction.
- **Hypothesis:** A minimal T1 check may improve only the extreme low-gap region, but the observed effect may be cohort noise.
- **Last validated:** Frozen trajectory rule 5 repairs/4 harms, net +1; INCONCLUSIVE.
- **Open risks:** Strong source heterogeneity; prompt-induced confidence inflation; selector harms; reused development sample.
- **Pending test:** Optional 326-call T1 bridge on the disjoint confirmatory low-gap cohort.
- **Kill criteria:** No tuning on trajectory100; retire T1 if bridge net ≤0, p≥0.05, or harms/repairs >0.50.
