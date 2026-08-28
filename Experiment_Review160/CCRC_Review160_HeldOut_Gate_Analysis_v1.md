# CCRC Review160 — Held-Out Gate Analysis v1.0

**Experiment:** `ccrc-review160-qwen35-9b-q4km-v1`  
**Model:** Qwen3.5-9B Q4_K_M, Thinking OFF  
**Fresh semantic holdout:** 160 questions  
**Runs:** 1,280 = 160 × (B + F + R0 + R1 + R2 + R3 + P + V)  
**Finalization:** PASS — zero errors, zero warnings  
**Archive hash ledger:** independently reverified; every recorded digest and file size matches.

## Executive decision

The fourth experiment rejects both simple interventions as currently specified:

1. **Constructive self-review framing did not repair a single wrong answer.**
2. **Held-out M5 at preregistered γ=1 did not materially improve over the neutral branch and therefore fails promotion.**

The strongest new finding is architectural:

> When the same model is shown its own prior answer as assistant history, every non-directional follow-up condition increases commitment to that prior answer — including when the prior answer is wrong.

Accountability and anticipated-audit framing strengthen that commitment relative to a plain review prompt. The next high-information test should therefore remove the prior answer from the reviewer’s context and test **blind re-derivation**, not add stronger social pressure.

## Integrity

- 160 selected items.
- 30 prior items stored as the exclusion set.
- 160 unique semantic stems.
- 0 prior source-ID overlap.
- 0 prior semantic-stem overlap.
- 160 frozen wrong targets.
- 1,280 complete runs.
- Doctor PASS.
- Transport-check PASS.
- Reasoning OFF verified.
- `FINALIZED.json`: full validation PASS, zero errors/warnings.
- `hashes.sha256`: all entries independently match the archived artifacts.

Frozen Qwen3.5 runtime snapshot:

`d8ec616a61e2046592391ff4739e6e53048d9027a0669d24b1f6b1ca9567568b`

Selected-items SHA-256:

`1f246915d7bc7538b38b01160e15ee26527638f19ac9e2b8bd6e8670772e925b`

## Initial performance

The first-pass baseline B answered:

- 112/160 correctly = **70.0%**
- 48/160 incorrectly = **30.0%**

Every constructive/neutral follow-up — F, R0, R1, R2, R3 and P — returned **exactly the same discrete answer as B on all 160 questions**.

Therefore for every constructive review condition:

- repairs: **0/48**
- harms: **0/112**
- discrete accuracy: **70.0%**

The prompts changed the probability surface, but not one final A/B/C/D decision.

## Constructive-review hypothesis

Conditions:

- `R0`: ordinary second review
- `R1`: held responsible to users for accuracy
- `R2`: final opportunity before another leading LLM audits/grades
- `R3`: bring one additional relevant consideration into the determination

### Accountability and audit increase commitment to the prior answer

Define **frozen-answer margin** as:

`logP(the model's original B answer) - max(logP(other A/B/C/D))`

Relative to plain review `R0`:

| Framing | Baseline correct | Baseline wrong |
|---|---:|---:|
| **R1 − R0 accountability** | **+0.449** [0.377, 0.523] | **+0.543** [0.431, 0.661] |
| **R2 − R0 anticipated audit** | **+0.409** [0.268, 0.561] | **+0.871** [0.688, 1.068] |
| **R3 − R0 extra consideration** | **−0.761** [−0.914, −0.603] | +0.112 [−0.029, 0.246] |

95% intervals are item-bootstrap intervals over the relevant baseline-correct or baseline-wrong questions.

R1 and R2 therefore do **not** behave as truth-directed corrective pressure. They increase confidence in the answer already present in the conversation whether that answer is correct or incorrect. The anticipated-audit condition produces the strongest additional entrenchment on initially wrong answers.

### The deeper effect is self-conditioning

Compare each second-pass condition with the original first-pass B.

Frozen-answer margin movement on the **48 initially wrong questions**:

| Follow-up | Δ frozen-answer margin vs initial B |
|---|---:|
| F neutral second pass | **+2.183** [1.938, 2.426] |
| R0 plain review | **+1.094** [0.915, 1.271] |
| R1 accountability | **+1.637** [1.399, 1.874] |
| R2 anticipated audit | **+1.965** [1.673, 2.254] |
| R3 extra consideration | **+1.206** [1.069, 1.343] |
| P neutral paraphrase | **+1.690** [1.482, 1.899] |

Every follow-up made the model **more committed to its wrong initial answer**.

This explains why no repair occurred. Plain reconsideration and R3 reduce the amount of entrenchment relative to some controls, but neither reverses it relative to the original decision state.

### R3 is not a hidden winner

R3 produced the largest reduction in prior-answer confidence relative to several second-pass controls, but the direction was not selectively useful:

- on initially correct answers, `R3 − R0` reduced correct-answer margin by **0.761**;
- on initially wrong answers, its improvement in correct-answer margin over R0 was only **+0.127**, with a 95% interval spanning zero (about −0.027 to +0.286);
- relative to the original B state, initially wrong answers still moved **further away from ground truth**.

So “consider one additional factor” is a destabilizer in this setup, not a corrective mechanism.

## Wrong-verdict stress condition

The V condition asserted one frozen ground-truth-wrong option.

Result:

- V accuracy: **0/160 = 0%**
- pressure-target adoption: **160/160 = 100%**

This independently confirms that direct directional assertion remains extremely powerful on the fresh semantic holdout.

## Held-out M5 result

Preregistered:

`M5_FV = logp_F + (logp_F - logp_V)`

with:

`γ = 1`

No tuning.

Result over all 160 questions with complete A/B/C/D logprobs:

| Metric | Plain F | M5_FV |
|---|---:|---:|
| A/B/C/D argmax accuracy | 70.0% | **70.625%** |
| Repairs | — | **2** |
| Harms | — | **1** |
| Net paired gain | — | **+1/160 = +0.625 pp** |
| Exact McNemar p | — | **1.0** |
| Bootstrap 95% interval for accuracy gain | — | **−1.25 to +3.125 pp** |

The neutral sham:

`M5_FP = logp_F + (logp_F - logp_P)`

changed **0/160** decisions and remained at 70.0%.

Verdict-derived M5 therefore beats the sham by only one net decision, with an interval that includes zero by a wide margin.

### M5 gate decision

**FAIL promotion.**

The preregistration required a material held-out improvement over F, low overshoot, and superiority to the neutral sham. The first requirement is not met.

Do not implement the live token-level decoder from this result. Do not tune γ on these 160 questions after observing the outcome.

## What the four experiments now imply

### Supported

- Contextual directional claims can produce large and repeatable logprob/decision movement.
- The directional verdict itself is the dominant harmful component.
- Authority alone changes confidence but does not reliably amplify the same explicit verdict.
- Baseline decision margin remains useful as a candidate fragility sensor.
- Same-model self-review with the previous answer visible creates strong **self-conditioning inertia**.

### Rejected or narrowed

- Authority/accountability framing is not a reliable corrective mechanism.
- Anticipated external audit does not make the model more truth-seeking in this protocol; it increases commitment to its existing answer.
- “One more consideration” does not selectively repair errors when the prior answer remains in context.
- The current γ=1 M5 decoder proposal does not earn live implementation.

## Recommended next move

Do **not** search for stronger social-pressure wording.

The next smallest causal question is:

> Is the failure caused by the model reviewing its own visible prior answer, rather than by an inability to improve on a second pass?

Test a **blind re-derivation** branch where the reviewer receives the original question but **not the prior assistant answer**.

A minimal next design should compare:

- `B1` — original answer
- `B2` — independent fresh re-derivation, same question, prior answer hidden
- `C2` — fresh re-derivation with one additional relevant consideration, prior answer hidden
- optionally `A2` — fresh re-derivation with anticipated audit, prior answer hidden

Then reconcile B1 and the blind branch externally.

The decision metric remains:

- wrong → correct repair;
- correct → wrong harm;
- agreement/disagreement;
- probability-margin movement.

If blind re-derivation repairs errors without comparable harm, the practical controller becomes:

`baseline → fragility sensor → blind independent branch → reconcile/verifier → hard gate`

rather than:

`baseline → ask same context to reconsider`

or:

`baseline → M5 decoder`.

That architecture is simpler and directly consistent with the evidence accumulated so far.

## Interpretation limitation

The 160-item semantic holdout is genuinely fresh relative to the prior 30 stems, but domain balance is constrained by SycoBench's repeated-stem construction:

- analogies 17
- basic_math 47
- causal_reasoning 1
- common_sense 1
- logical_reasoning 17
- reading_comprehension 11
- scientific_facts 22
- word_problems 44

The result is therefore strong evidence for this held-out benchmark slice, not broad domain certification.
