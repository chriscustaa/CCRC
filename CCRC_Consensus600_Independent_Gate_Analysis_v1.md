# CCRC Consensus600 — Independent Gate Analysis v1.0

**Experiment:** `ccrc-consensus600-qwen35-9b-q4km-v1`  
**Model:** Qwen3.5-9B Q4_K_M, Thinking OFF  
**Dataset:** 600 fresh MMLU test questions across 57 subjects  
**Frozen thresholds:** primary θ = 0.20; secondary θ = 0.50  
**Recorded rows:** 1,332  
**Finalization:** PASS — zero validation errors/warnings

## Executive decision

The strongest result is not the consensus mechanism. It is the **decision-margin sensor**.

On a new benchmark distribution, the frozen pre-answer top-two answer-logprob gap strongly separated reliable from unreliable first-pass decisions:

- overall B1 accuracy: **77.17%**
- `g < 0.20`: **25.93% correct / 74.07% wrong**
- `0.20 <= g < 0.50`: **28.21% correct**
- `g >= 0.50`: **83.33% correct**
- exploratory ROC AUC for **low gap predicting B1 error**: **0.875**, bootstrap 95% CI ≈ **0.845–0.902**

This is a strong cross-dataset replication that the margin is a useful **pre-answer fragility/error-risk sensor** in a finite-choice decision space.

The frozen θ=.20 adaptive controller also passes its preregistered kill rule, but only narrowly and with small disagreement counts. It should be replicated before production promotion.

## 1. Integrity and provenance

Independent archive audit:

- 600 frozen items.
- 1,332 run records.
- 600 B1 rows.
- 600 D0 rows.
- 66 V1 rows.
- 66 V2 rows.
- 66 items had `g < 0.50`.
- 27 items had `g < 0.20`.
- 57 MMLU subjects represented with 10–11 items each.
- prior SycoBench semantic-stem overlap: 0.
- 631 permutation-unsafe MMLU rows excluded before sampling.
- MMLU source parquet SHA-256:
  `c08ff89872eac44b092e2e94a17d7a7c358f5a27c52241b60748830a81561c8b`
- runtime snapshot:
  `d8ec616a61e2046592391ff4739e6e53048d9027a0669d24b1f6b1ca9567568b`
- Doctor: PASS.
- Transport check: PASS.
- Reasoning-off telemetry: no hidden reasoning detected.
- Every entry in `hashes.sha256` independently matches the archived bytes.
- Every file/size digest asserted by `FINALIZED.json` independently matches.

## 2. The margin sensor generalized

Initial B1:

- correct: **463/600**
- wrong: **137/600**
- accuracy: **77.17%**

### Frozen sensor strata

| B1 gap | n | B1 accuracy | B1 error rate |
|---|---:|---:|---:|
| `g < .20` | 27 | **25.93%** | **74.07%** |
| `.20 <= g < .50` | 39 | **28.21%** | **71.79%** |
| `g >= .50` | 534 | **83.33%** | **16.67%** |

Wilson 95% intervals for B1 accuracy:

- `g < .20`: ≈ 13.2%–44.7%
- `.20 <= g < .50`: ≈ 16.5%–43.8%
- `g >= .50`: ≈ 79.9%–86.3%

Using low gap as an error-risk score, exploratory ROC AUC is **0.875** (bootstrap 95% CI ≈ 0.845–0.902).

At the frozen thresholds:

- θ=.20 routed only **4.5%** of questions.
  - 74.1% of routed B1 answers were wrong.
  - It captured 14.6% of all B1 errors.
- θ=.50 routed **11.0%**.
  - 72.7% of routed B1 answers were wrong.
  - It captured 35.0% of all B1 errors.

The sensor therefore concentrated error risk by roughly **3.2×** relative to the overall B1 error rate.

## 3. Extra inference was useful only in the extreme-low-margin region

### `g < .20`

B1:

- 7/27 correct = **25.93%**

D0:

- 12/27 correct = **44.44%**
- repairs: **7**
- harms: **2**
- net: **+5**

### `.20 <= g < .50`

B1:

- 11/39 correct = **28.21%**

D0:

- 10/39 correct = **25.64%**
- repairs: **4**
- harms: **5**
- net: **−1**

### `g >= .50`

B1:

- 445/534 correct = **83.33%**

D0:

- 439/534 correct = **82.21%**
- repairs: **3**
- harms: **9**

This is a direct empirical argument for **adaptive allocation rather than universal reconsideration**.

The low-margin sensor does not merely identify a weak state. At the preregistered `.20` boundary it identified the region where blind re-derivation had positive observed value, while broader application erased or reversed that value.

## 4. Primary θ=.20 controller

### Baseline B1

`463 correct / 137 wrong`

Accuracy: **77.17%**

### Gated direct D0

Only 27/600 questions routed.

Result:

`468 correct / 132 wrong`

- repairs: **7**
- harms: **2**
- net gain: **+5 decisions**
- accuracy: **78.00%**
- absolute gain over B1: **+0.83 pp**

The paired effect is still statistically uncertain:

- exact McNemar p ≈ **0.180**
- item-bootstrap 95% interval for the accuracy gain ≈ **−0.17 to +1.83 pp**

So this is favorable evidence, not accuracy certification.

### Gated blind consensus

There were only **15 B1/D0 disagreements** inside the θ=.20 gate.

Final outcome:

`468 correct / 129 wrong / 3 abstain`

- repairs relative to B1: **6**
- harmful flips: **1**
- net repairs − harms: **+5**
- coverage: **99.5%**
- accuracy among answered: **78.39%**
- resolved-correct / total: **78.00%**

### Frozen kill rule

The preregistered rule required consensus to:

1. reduce D0 harms; and
2. preserve a positive net gain over B1.

Observed:

- direct D0 harms: **2**
- consensus harms: **1**
- consensus net repairs − harms: **+5**

**Primary frozen kill rule: PASS.**

This is a narrow pass: only 15 disagreements entered the reconciliation stage.

## 5. What consensus actually bought

Compared directly with θ=.20 gated D0:

| Outcome | Direct D0 | Blind consensus |
|---|---:|---:|
| Correct | **468** | **468** |
| Wrong released | 132 | **129** |
| Abstain | 0 | **3** |

So consensus did **not** increase the number of correct answers in this sample.

It converted three wrong releases into non-wrong outcomes while preserving the same total number of correct answers, at the cost of three abstentions.

The item-level transition matrix from direct D0 to consensus was:

- correct → correct: 466
- wrong → wrong: 129
- wrong → correct: 2
- wrong → abstain: 1
- correct → abstain: 2

Therefore consensus is presently best interpreted as a **risk/abstention layer**, not an accuracy multiplier.

Ignoring compute cost, consensus is preferable to direct D0 whenever the utility of abstention is meaningfully higher than the utility of releasing a wrong answer.

## 6. θ=.50 comparator

Direct θ=.50:

`467 correct / 133 wrong`

It routed 66 questions, used more computation, and produced **one fewer correct answer** than θ=.20 direct.

Thus the earlier domination result for direct substitution survives this new distribution.

Consensus θ=.50:

`468 correct / 127 wrong / 5 abstain`

Compared with θ=.20 consensus:

- correct count: unchanged at 468
- wrong releases: 129 → **127**
- abstentions: 3 → **5**
- substantially more compute

So consensus changes the utility frontier: θ=.50 can trade two additional wrong releases for two abstentions, but it does not add correct answers.

Within the previously questionable `.20 <= g < .50` region alone:

- B1: 11 correct / 28 wrong
- D0: 10 correct / 29 wrong
- consensus: 11 correct / 26 wrong / 2 abstain

Consensus removes the direct-D0 harm in correct-count terms, but does **not** improve correct count over B1. Whether this region is worth routing depends on the relative cost of a wrong answer, an abstention, and extra inference.

## 7. Blind branch diversity

Across the 66 `g < .50` items:

| Branch | Accuracy |
|---|---:|
| B1 | 27.27% |
| D0 | 33.33% |
| V1 | **39.39%** |
| V2 | **40.91%** |

Pairwise answer agreement:

- D0–V1: 53.0%
- D0–V2: 62.1%
- V1–V2: 48.5%

Correctness correlations were moderate rather than near-perfect:

- D0–V1: ≈ 0.35
- D0–V2: ≈ 0.52
- V1–V2: ≈ 0.40

The same-model branches are not independent, but the option permutations and neutral prompt variation generated enough diversity for consensus to have nonzero reconciliation value.

Exploratory only: on the 27 `g < .20` items, V2 alone reached 16/27 = **59.3%**. This was not a preregistered policy and should not be promoted from this result.

## 8. Important cost-accounting defect

There is one material harness issue that does **not** invalidate the sensor result but must be corrected before the next controller run.

**39/600 D0 rows failed the one-letter format on the first call and triggered a second format-retry inference.**

The finalized archive correctly preserves those retries inside each row, but the generated policy cost summary counts each D0 row as one call and omits retry tokens.

Therefore:

### Actual inference-call accounting

| Policy | Generated summary | Corrected actual calls |
|---|---:|---:|
| θ=.20 direct | 627 | **630** |
| θ=.20 consensus | 657 | **660** |
| θ=.50 direct | 666 | **674** |
| θ=.50 consensus | 726 | **734** |

Actual experiment generation calls:

- recorded rows: 1,332
- D0 retry calls: 39
- **actual generation calls: 1,371**

### Corrected token accounting

| Policy | Generated summary | Corrected tokens |
|---|---:|---:|
| θ=.20 direct | 80,920 | **81,380** |
| θ=.20 consensus | 84,732 | **85,192** |
| θ=.50 direct | 86,090 | **87,231** |
| θ=.50 consensus | 93,472 | **94,613** |

Three of the 27 primary-gate D0 items required a retry.

Sensitivity analysis excluding those three primary-gate retry cases:

- D0 on the remaining 24: **6 repairs / 1 harm**
- so the positive low-margin D0 effect survives qualitatively.
- consensus becomes weaker on that restricted set: **4 repairs / 1 harm / 3 abstentions**.

Future harnesses should either enforce finite-choice output structurally or account for retry calls/tokens explicitly in EVC and policy cost.

## 9. Decision

### Decision-margin sensor

**STRONG PASS as a research sensor.**

It replicated on a new 57-subject distribution and strongly stratified first-pass error risk before any corrective branch was applied.

### θ=.20 gated D0

**PROMOTE for confirmatory replication.**

The effect is directionally consistent and compute-efficient, but the routed sample is only 27 items.

### Blind consensus

**PASS the frozen kill rule; do not production-promote yet.**

It reduced harmful flips and wrong releases without reducing total correct count, but the result rests on 15 reconciliation events and is partially affected by D0 format-retry heterogeneity.

### θ=.50 direct

**REJECT.**

More compute, fewer correct answers than θ=.20 direct.

### θ=.50 consensus

**UTILITY-DEPENDENT, not accuracy-promoted.**

It exchanged two additional wrong releases for two abstentions relative to θ=.20 consensus, with no increase in correct count.

## 10. Research implication

The most consequential result of Experiment 6 is now:

> **The system can identify a small subset of decisions before final release in which the model is wrong roughly three-quarters of the time, and extra cognition has positive observed value only in the most fragile part of that subset.**

That is substantially closer to an adaptive inference controller than a generic confidence score.

The present finite-choice architecture is:

`B1 sensor → if g<.20 allocate blind D0 → if disagreement allocate blind reconciliation → release / abstain`

The next replication should keep θ=.20 frozen, fix the D0 output/retry issue, and collect materially more low-margin and disagreement cases without tuning the policy on the new results.
