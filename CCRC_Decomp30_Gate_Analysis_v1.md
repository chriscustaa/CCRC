# CCRC Decomp30 — Gate Analysis v1.0

**Experiment:** `ccrc-decomp30-qwen35-9b-q4km-v1`  
**Model:** Qwen3.5-9B Q4_K_M, Thinking OFF  
**Runs:** 540 = 30 questions × 3 template families × 6 conditions  
**Finalization:** PASS; 30 items, 30 targets, 540 runs, zero errors/warnings  
**Hash ledger:** independently reverified against the archived files; all entries match.

## Decision

The decomposition answered the causal question cleanly:

1. **Directional verdict effect (V-F): PASS — very large and stable.**
2. **Authority amplification of the same verdict (AV-V): FAIL — not stable across template families and essentially zero on the primary logprob endpoint.**
3. **Authority-only effect (A-F): PASS as a smaller, non-directional destabilization effect.**
4. **Neutral wording floor (P-F): small.**

The original broad “social hierarchy / authority pressure” hypothesis therefore needs to be narrowed. Authority status does alter the model’s uncertainty state, but the large harmful directional movement is caused primarily by the asserted verdict itself, not by authority amplifying that verdict.

## Primary endpoint

Primary directional endpoint:

`Δ [ logP(pressure_target) - logP(correct) ]`

Question-cluster bootstrap intervals resample the 30 question IDs while preserving all three template families.

| Contrast | Mean Δ | 95% cluster-bootstrap interval | Template-family means |
|---|---:|---:|---|
| **A-F** | **+0.674** | **+0.559 to +0.792** | +0.446, +0.541, +1.034 |
| **V-F** | **+7.663** | **+6.893 to +8.382** | +8.798, +4.111, +10.080 |
| **AV-V** | **−0.126** | **−0.303 to +0.041** | −0.573, +0.857, −0.660 |
| **AV-F** | **+7.537** | **+6.747 to +8.275** | +8.225, +4.967, +9.419 |
| **P-F** | **+0.102** | **+0.020 to +0.184** | −0.160, +0.327, +0.138 |

Relative to the neutral wording control:

- `(V-F) − (P-F) = +7.561`, 95% CI `+6.792 to +8.301`
- `(A-F) − (P-F) = +0.572`, 95% CI `+0.433 to +0.728`
- `(AV-V) − (P-F) = −0.227`, 95% CI `−0.435 to −0.020`

So the explicit wrong verdict dwarfs ordinary wording variation. Authority amplification does not.

## Discrete behavior

Condition-level accuracy / target adoption:

| Condition | Accuracy | Pressure-target adoption |
|---|---:|---:|
| F — neutral source | 92.2% | 3.3% |
| A — authority only | 91.1% | 3.3% |
| V — wrong verdict | **21.1%** | **77.8%** |
| AV — authority + same wrong verdict | **16.7%** | **83.3%** |
| P — neutral paraphrase | 91.1% | 3.3% |

Paired target-adoption change:

- `V-F`: **+74.4 percentage points**
- `AV-F`: **+80.0 pp**
- `A-F`: **0.0 pp**
- `P-F`: **0.0 pp**
- `AV-V`: **+5.6 pp**, but this entire increment came from template family 1; families 0 and 2 were exactly 0. This fails the predeclared cross-template stability criterion.

## Authority-only effect

`A-F` is real but qualitatively different from the verdict effect.

Correct-answer margin changed by:

- `A-F`: **−0.626**, 95% CI `−0.753 to −0.508`
- `P-F`: **−0.081**, 95% CI `−0.154 to −0.006`

Across the restricted A/B/C/D distribution, authority-only context:

- increased entropy by about **+0.069 nats**;
- reduced probability assigned to the correct option by about **3.38 percentage points**;
- almost never changed the discrete answer.

Interpretation: authority identity appears to induce **reconsideration / confidence flattening**, not directional movement toward a particular wrong option.

That is a much narrower and more defensible claim than “authority creates a directional pressure vector.”

## Gate result

The frozen v0.3 decision rule was:

> M5 remains blocked unless a pressure contrast is stable across variants and exceeds neutral P-F wording variation.

`V-F` passes this rule decisively.

Therefore:

**M5 is now unblocked only for a bounded proof-of-concept targeting directional-verdict contamination.**

It is **not** justified as an “authority correction” mechanism. The authority-amplification hypothesis failed the primary stability test.

## Zero-cost M5 feasibility check from the existing logits

Before requesting another model call, I evaluated the candidate-level analogue of the original M5 rule using the already-collected A/B/C/D logprobs:

`z_guided = z_F + gamma * (z_F - z_V)`

At the natural preregistration-friendly value `gamma = 1`:

- neutral F argmax accuracy: **92.2%**
- guided argmax accuracy: **96.7%**
- **4/90** condition-variant rows were corrected
- **0/90** previously correct F rows were harmed
- pressure-target adoption fell from 3.3% to **0%**

However, the four fixes cluster on only two question IDs. A question-cluster bootstrap for the +4.44 pp accuracy change has an interval of approximately **0 to +12.2 pp**.

A deterministic 15-question/15-question internal split gave:

- calibration: 93.3% → 100%
- held-out half: **91.1% → 93.3%**

This is promising, but it is not enough to claim M5 adds value beyond the neutral branch. The sample was used to discover the mechanism, and the apparent gain depends on only a few items.

## Recommended next experiment

Do **not** build a general decoder yet, and do not spend the next run repeating all 540 decomposition calls on Qwen2.5.

The highest-information next test is a **fresh held-out M5 Pilot-1** on new SycoBench questions.

Suggested design:

- Qwen3.5-9B, identical frozen runtime.
- Exclude all current 30 questions.
- Freeze **160 fresh questions** before analysis.
- Use a **new matched template family** not used in Decomp30.
- Collect only:
  - `F` neutral source/no verdict
  - `V` same source + frozen wrong verdict
  - `P` neutral paraphrase/sham contrast
- Shared ground-truth-correct assistant prefix.
- Temperature 0, Thinking OFF, same logprob capture.
- Predeclare **gamma = 1**. No gamma tuning on the held-out set.

Primary test:

`accuracy(M5_FV) - accuracy(F)`

where:

`M5_FV = z_F + (z_F - z_V)`

Mandatory sham control:

`M5_FP = z_F + (z_F - z_P)`

The verdict-derived correction must outperform both:

1. plain `F`, and
2. the neutral-paraphrase extrapolation `M5_FP`.

Also track:

- F-correct → M5-wrong harms;
- F-wrong → M5-correct repairs;
- pressure-target adoption;
- correct-answer margin;
- per-question paired exact/McNemar inference.

### Kill criterion

If verdict-derived M5 does not materially outperform the neutral F branch on fresh questions, or if sham `F-P` extrapolation performs similarly, **kill the decoder idea** and keep the simpler architecture:

`fragility / margin sensor → neutralized branch / verifier → hard gate`.

### Promotion criterion

If M5 improves held-out accuracy with low overshoot and beats the sham contrast, then build the first live token-level M5 implementation and only afterward replicate the causal mechanism on Qwen2.5.

## Research-state update

**Promoted**
- Directional suggestion is the dominant causal pressure component.
- Authority identity independently flattens confidence.
- Authority does not reliably amplify an explicit wrong verdict.
- Query-local contrastive correction has a promising offline signal.

**Rejected / narrowed**
- “Authority pressure” should not be treated as one directional nuisance vector.
- A hierarchy-specific M5 intervention is not supported.
- Full decoder implementation is still premature.

**Next irreversible commitment:** none.  
The next step should remain a cheap, held-out, falsifiable test.
