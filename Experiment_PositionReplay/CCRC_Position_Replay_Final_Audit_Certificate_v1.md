# CCRC Position-Balanced Replay — Final Audit Certificate v1

**Audit date:** 2026-08-26  
**Result archive:** `experiment_position_replay_final.zip`  
**Archive SHA-256:** `265daf8677160bd3a8af43a1acc36c8352e40fcca898875bdd72fbc3d2ca178b`  
**Harness:** `ccrc-position-replay` v0.7.0  
**Model lineage:** Qwen3.5 9B Q4_K_M, thinking off  
**Runtime snapshot SHA-256:** `d8ec616a61e2046592391ff4739e6e53048d9027a0669d24b1f6b1ca9567568b`

## Verdict

**PASS. The current no-I5, θ=.20 verifier actuator survives the frozen position-balanced kill rule and qualifies for one fresh powered confirmatory experiment.**

This replay stabilizes the topology; it does not confirm efficacy. No threshold tuning, I5 branch, eight-output vote, or new verifier framing is authorized by this result.

## Integrity reconstruction

- ZIP integrity test: PASS.
- Every archive-level SHA-256 entry: PASS.
- Every frozen-input SHA-256 entry: PASS.
- Frozen manifest matches the trusted pre-outcome package exactly.
- Independent v0.7.0 full validation: PASS, zero errors.
- Independent regeneration of `analysis.json`, `validation.json`, and `cell_results.csv`: byte-identical to the submitted results.
- Planned/completed cells: 568/568.
- Unique run keys: 568.
- Actual model calls: 568; format retries: 0.
- Exact one-letter outputs: 568/568.
- Reasoning telemetry: 0/568.
- Seeds sent: 568/568; seed rejections: 0.
- Model and runtime snapshot matches: 568/568.
- Stateful continuation and prior-answer exposure: 0.

## Position and representation finding

Each of 71 items was tested at all four correct-answer display slots in each of two identical-wording replicate streams.

| Correct display slot | Correct / cells | Accuracy |
|---|---:|---:|
| A | 55 / 142 | 38.73% |
| B | 46 / 142 | 32.39% |
| C | 88 / 142 | 61.97% |
| D | 86 / 142 | 60.56% |

Within-item paired contrasts from the frozen analysis:

- B versus C: −29.58 percentage points; exact sign p=`5.72e-6`.
- B versus D: −28.17 points; p=`0.000535`.
- A versus C: −23.24 points; p=`0.00151`.
- A versus D: −21.83 points; p=`0.00904`.
- C versus D: +1.41 points; p=`1.0`.
- A versus B: +6.34 points; p=`0.523`.

An auxiliary item-level Friedman test gives χ²=`26.47`, p=`7.60e-6`. This omnibus calculation was not the frozen primary endpoint and is recorded as supportive.

Display choices were A=`135`, B=`80`, C=`182`, D=`171`, versus 142 expected per slot under uniform choice. The earlier simple “display-C preference” description is therefore incomplete: the replay identifies a broader high-slot C/D versus low-slot A/B representation effect in this design.

Fifty-six of 71 items (78.9%) produced more than one canonical answer across their eight cells; 17/71 produced at least three. Yet identical-placement R1/R2 answers agreed on 283/284 pairs (99.65%). The one disagreement occurred on `mmlu-0556`, placement P1. This combination—high repeat stability at a fixed representation and high answer movement across representations—supports a causal position/representation effect rather than verifier wording or ordinary sampling noise.

The exact slot ranking should not be universalized across datasets: consensus600 and I5-1000 did not share an identical rank order. The durable finding is representation sensitivity, not that one named display letter is always best.

## Frozen controller reconstruction

### Primary: deduplicated 942-item cohort

- Baseline B0 correct: 735.
- θ=.20 routed: 33.
- B0–D0 verifier escalations: 18.
- Uniform position-balanced expected repairs: 6.0625.
- Expected harms: 2.9375.
- Expected net repairs: **+3.125**.
- Expected strict correct: 738.125; overall expected gain: +0.332 percentage points.

Across all `21,449,372,440,854,758,400` valid globally balanced schedules:

- net positive: **99.4078%**;
- net exactly zero: 0.5571%;
- net negative: 0.0351%.

The frozen rule required expected net `>0` and at least 95% of valid schedules with net `>0`. Both conditions pass.

### Secondary: complete 1,000-item cohort

- Baseline B0 correct: 781.
- Routed: 35; escalated: 20.
- Expected repairs: 6.125.
- Expected harms: 2.9375.
- Expected net: +3.1875.
- Positive balanced schedules: 99.4517%.

The balanced replay therefore does not explain away the earlier 6-repair/3-harm controller result. It confirms that the global verifier accuracy was position-sensitive while the controller's net sign remained robust to position balancing.

## Evidentiary boundary

The controller result remains conditional on previously exposed MMLU items and frozen B0/D0 outcomes. The replay used these items intentionally to identify the position mechanism. It is not an independent efficacy replication and should not be pooled into a confirmatory claim.

The justified conclusion is:

> The verifier actuator is position-sensitive but its expected corrective net remains stably positive after balancing, so the topology may proceed to fresh confirmation.

## Confirmatory power basis

Using the stabilized deduplicated primary estimates:

- overall repair probability: `6.0625 / 942 = 0.006436`;
- overall harm probability: `2.9375 / 942 = 0.003118`;
- paired-discordance probability: `0.009554`;
- repair probability conditional on a paired discordance: `0.67361`.

For a one-sided exact McNemar test at α=.05, unconditional exact power under those point estimates is approximately:

| Fresh items | Power |
|---:|---:|
| 2,400 | 43.6% |
| 5,000 | 74.2% |
| 5,775 | 80.0% |
| 7,500 | 88.8% |
| 7,818 | 90.0% |

These are planning estimates, not evidence; regression toward a smaller fresh-sample effect remains possible. The lower-risk recommendation is a fixed fresh cohort of approximately **7,818 items** for 90% point-estimate power, subject to a separate frozen availability and overlap audit before execution.

## Authorized next topology

- No I5.
- B0 sensor and θ=.20 unchanged.
- D0 bridge unchanged.
- On B0–D0 disagreement, two identical-wording blind verifiers.
- Independent deterministic option permutations generated without using truth.
- Majority `(D0, V1, V2)`; three-way split abstains.
- Primary endpoint: paired strict-accuracy change versus B0, tested one-sided by exact McNemar repairs versus harms.
- Primary arm named in advance: the consensus controller above.
- Fresh stems must exclude the frozen union of 1,812 prior exact MCQs.

The confirmatory protocol must be frozen before any new outcomes. If the fresh primary endpoint fails, retire the efficacy claim rather than tune θ, prompts, slot schedules, or endpoints.

