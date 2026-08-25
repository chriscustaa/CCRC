# CCRC Blind80 — Gate Analysis v1.0

**Experiment:** `ccrc-blind80-qwen35-9b-q4km-v1`  
**Model:** Qwen3.5-9B Q4_K_M, Thinking OFF  
**Fresh semantic holdout:** 80 questions after excluding 190 prior semantic stems  
**Runs:** 560 = 80 × (B + S0 + D0 + D1 + D2 + D3 + DP)  
**Finalization:** PASS — zero errors, zero warnings  
**Archive integrity:** every entry in `hashes.sha256` independently reverified.

## Executive decision

The fifth experiment supports the **self-conditioning / prior-answer visibility mechanism**, but does **not** yet justify unconditional blind re-derivation as a production controller.

The main finding is:

> Hiding the model's prior answer causes a substantial de-anchoring movement. That movement is beneficial when the prior answer is wrong and detrimental when the prior answer is correct.

This makes the previously discovered baseline-margin/fragility sensor more important. The next controller to test should therefore be **sensor-gated blind re-derivation**, not blind re-derivation on every query.

## Integrity

- 80 selected items.
- 190 prior items/stems excluded.
- 80 unique fresh semantic stems.
- 560 complete runs.
- Doctor PASS.
- Transport-check PASS.
- Reasoning OFF preserved.
- `FINALIZED.json`: full validation PASS, zero errors/warnings.
- Hash ledger: all 12 archived entries match independently recomputed SHA-256 digests.

Frozen runtime snapshot:

`d8ec616a61e2046592391ff4739e6e53048d9027a0669d24b1f6b1ca9567568b`

Selected-items SHA-256:

`cec194ee1445611160523d5defdd4ef5ad1246d69953325cb9a484a9c708e338`

## Baseline

Initial B accuracy:

- 55/80 correct = **68.75%**
- 25/80 wrong = **31.25%**

## Primary contrast: blind D0 vs visible-self S0

| Metric | S0 — prior answer visible | D0 — prior answer hidden |
|---|---:|---:|
| Accuracy | 68.75% | **71.25%** |
| Agreement with original B | 98.75% | **91.25%** |
| B-wrong → correct repairs | 0/25 | **4/25 (16.0%)** |
| B-correct → wrong harms | 0/55 | **2/55 (3.64%)** |

Direct paired accuracy difference:

`D0 - S0 = +2.5 percentage points`

Item-bootstrap 95% interval:

`−3.75 to +8.75 pp`

Direct D0/S0 discordant correctness pairs:

- D0 correct / S0 wrong: **4**
- S0 correct / D0 wrong: **2**
- exact McNemar p = **0.6875**

So the discrete improvement is directionally favorable but not statistically decisive.

## Probability-surface result

The probability surface gives a much cleaner causal signal.

### When the original B answer was wrong (n=25)

Hiding the prior answer (`D0-S0`):

- changed correct-answer margin by **+0.800**
- 95% item-bootstrap interval: **+0.543 to +1.080**
- changed frozen-B margin by **−0.569**
- 95% interval: **−0.870 to −0.288**

The blind branch therefore moved probability **away from the wrong prior answer and toward ground truth**.

### When the original B answer was correct (n=55)

Hiding the prior answer:

- changed correct-answer margin by **−0.506**
- 95% interval: **−0.742 to −0.277**

Because the frozen B answer is correct in these cases, this is simultaneously a reduction in frozen-B margin.

The blind branch therefore also moved probability **away from a correct prior answer**.

### Interpretation

Blind re-derivation is not a truth detector.

It is a **de-anchoring intervention**:

`visible prior answer → stronger commitment`

`prior answer hidden → weaker commitment / renewed local search`

That helps when the anchor is wrong and hurts when the anchor is right.

## Fragility sensor replication

All **7** cases where D0 changed the original discrete answer had very low first-pass top-two A/B/C/D gaps:

`0.021, 0.136, 0.145, 0.166, 0.269, 0.288, 0.469`

No D0 answer change occurred above a baseline gap of 0.469.

Median baseline top-two gap:

- D0 changed B: **0.166**
- D0 preserved B: **1.792**

Spearman correlation between baseline gap and whether D0 changed the answer:

`ρ = −0.453, p ≈ 2.44×10⁻⁵`

Baseline gap also discriminated initial correctness on this fresh holdout with exploratory ROC AUC ≈ **0.82**.

This extends the earlier fragility-sensor finding to a new semantic holdout and a different intervention class.

## Social framing inside the blind branch

Relative to plain blind D0:

| Condition | Accuracy change vs D0 |
|---|---:|
| D1 accountability | **−2.5 pp** |
| D2 anticipated LLM audit | **0.0 pp** |
| D3 extra consideration | **−6.25 pp** |
| DP blind paraphrase | **−2.5 pp** |

D3 was clearly harmful in this sample; its bootstrap interval for the paired accuracy change relative to D0 was approximately **−12.5 to −1.25 pp**.

D2 matched D0's discrete accuracy but did not improve repair/harm counts and added no evidence that social pressure helps once the prior answer is hidden.

**Plain blind D0 remains the strongest branch.**

## Gate decision

### Causal mechanism

**PASS.**

Prior-answer visibility measurably anchors the model. Removing the prior answer produces a strong de-anchoring shift whose direction relative to ground truth depends on whether the original answer was correct.

### Unconditional blind-rederivation controller

**NOT PROMOTED TO PRODUCTION.**

Point estimates satisfy the preregistered directional rule (4 repairs > 2 harms; +2.5 pp paired accuracy), but only six correctness-discordant D0/S0 items drive the gain and the confidence interval includes zero.

### Sensor-gated blind re-derivation

**PROMOTE TO THE NEXT EXPERIMENT.**

The accumulated evidence now supports the architecture:

`baseline → margin/fragility sensor → blind re-derivation only when fragile → reconcile/verifier → hard gate`

rather than blind re-derivation on all queries.

## Activation-steering implication

Blind80 produced four clean `B wrong → D0 correct` repair pairs and two D0 harms.

These are valuable causal transition examples, but **four successful repair pairs are far too few to learn or validate a general activation-space correction vector**.

The transition cases should be preserved. Hidden-state instrumentation should wait until a new benchmark supplies a materially larger set of verified failure→repair pairs.

## Recommended next experiment

SycoBench is now effectively exhausted for semantic holdout work. Move to a genuinely new MCQ source.

The next experiment should test a frozen **sensor-gated blind policy**:

1. Generate baseline B on a large fresh question pool.
2. Compute the baseline top-two answer gap before any review.
3. Apply blind D0 only to a preregistered low-margin region.
4. Preserve B for high-margin items.
5. Compare the resulting routed policy with:
   - baseline B;
   - unconditional D0;
   - a matched high-margin D0 control subset.
6. Track repairs, harms, disagreement, logprob-margin movement, and verifier escalation rate.

The routing threshold must be frozen before examining the new dataset. Blind80 can serve as calibration data; the next dataset must be treated as the held-out evaluation.

If sensor-gated D0 improves accuracy with materially lower overshoot than unconditional D0, the simple controller has earned implementation. If not, stop treating blind re-derivation as a corrective actuator.

## Benchmark limitation

After the previous exclusions, Blind80 contains:

- analogies: 9
- basic_math: 23
- logical_reasoning: 9
- reading_comprehension: 5
- scientific_facts: 12
- word_problems: 22

There were no fresh causal-reasoning or common-sense semantic stems left in SycoBench. Broad-domain replication must therefore use a different source.
