# CCRC Research State

**Repository:** `chriscustaa/CCRC`  
**Status:** Active, early-stage research  
**Purpose of this file:** Provide a compact authoritative checkpoint for fresh research sessions. Use primary experiment artifacts and analysis files for evidence; use this file for current state, active hypotheses, and next-step orientation.

## 1. Anchor

CCRC studies whether runtime signals can identify context-induced decision fragility and selectively trigger additional cognition or local intervention without making the model blindly contrarian, globally overcorrected, or unnecessarily expensive.

The core target is **conditional invariance**:

- remain stable when context should not change the answer;
- remain updateable when new evidence should change it;
- treat confidence or logprob margin as a fragility signal, not proof of correctness;
- intervene only when expected repair value exceeds harms and added inference cost.

## 2. Validated findings so far

### Syco30 / v0.1.3
- Qwen2.5-7B Q4_K_M on 30 SycoBench items.
- Baseline accuracy: 83.3%.
- Pressure-robust accuracy: 26.7%.
- Baseline answer margin strongly predicted later context-induced answer changes.
- Conclusion: susceptibility is measurable; the sensor was exploratory and causal intervention remained blocked.

Primary report: `Syco30_Qwen2.5_PostRun_Analysis_v1.md`

### Cross-model / v0.2.0
- Same 30 items on Qwen3.5-9B Q4_K_M.
- Baseline accuracy remained 83.3%.
- Pressure-robust accuracy rose to 50.0%.
- The margin/susceptibility relationship replicated with attenuation.
- Conclusion: advance to matched causal decomposition.

Primary report: `Syco30_Qwen35_CrossModel_Analysis_v1_1_CORRECTED.md`

### Decomp30 / v0.3.0
- 30 questions × 3 template families × 6 conditions; 540 runs.
- A wrong directional verdict caused the dominant shift.
- Authority alone mainly flattened confidence.
- Authority did not reliably amplify the verdict.
- Conclusion: reject a broad authority-bias claim; retain only a bounded verdict-contamination hypothesis.

Primary report: `CCRC_Decomp30_Gate_Analysis_v1.md`

### Review160 / v0.4.0
- 160 held-out SycoBench items; 1,280 runs.
- Visible self-review repaired 0/48 initial errors.
- Preregistered M5 at `γ=1` produced a net `+1/160` decision gain and its interval included zero.
- Conclusion: reject visible constructive review as an error-correction mechanism in this setting; do not promote M5.

Primary report: `CCRC_Review160_HeldOut_Gate_Analysis_v1.md`

### Blind80 / v0.5.0
- 80 fresh semantic stems; 560 runs.
- Hiding the prior answer produced 4 repairs and 2 harms.
- Blind D0 accuracy was 71.25% versus 68.75% for visible-self S0; paired uncertainty included zero.
- Conclusion: blind re-derivation is a de-anchoring actuator, not a truth detector.

Primary report: `CCRC_Blind80_Gate_Analysis_v1.md`

## 3. Current controller hypothesis

The strongest current architecture is not a universal steering vector or unconditional second pass. It is:

[
	ext{Sense} ightarrow 	ext{Allocate Cognition} ightarrow 	ext{Answer}
]

The current fragility sensor is the baseline top-two A/B/C/D logprob gap:

[
g(q) = log p(a_1|q) - log p(a_2|q)
]

Low-gap items may receive blind re-derivation. Disagreements may escalate to blind verification.

Important constraint: `g(q)` is a routing signal only. It must never be interpreted as evidence that the top answer is correct.

## 4. Current frozen experiment

### I5 × gated controller / v0.6.0
- 2×2 frozen design.
- 1,000 subject-balanced MMLU items.
- Tests a compact five-principle instruction layer independently and in combination with the sensor-gated blind-verifier controller.
- Current status in the repository: preregistered / pending final outcome.

Primary preregistration:

`ccrc_i5gated_harness_v0_6_0_qwen35/PREREGISTRATION.md`

Do not alter frozen thresholds, prompts, selection rules, model/runtime settings, or analysis gates after inspecting outcomes.

## 5. Active unresolved hypothesis

The Review160 result created an important ambiguity:

Visible constructive interventions applied **after a model has already committed to an answer** may reinforce self-conditioning rather than repair errors.

This motivates a bounded timing hypothesis:

[
	ext{precommitment intervention} 
eq 	ext{postcommitment intervention}
]

The current working interpretation is:

- postcommitment responsibility/audit/additional-consideration prompts failed completely as repair mechanisms on the 48 baseline-wrong Review160 cases;
- that result does **not** establish that the same framing has no value before initial commitment;
- therefore intervention timing / commitment state remains unresolved.

This is a hypothesis, not a validated result.

## 6. Next planned test after the frozen cycle

Run a small **precommitment / no-prior-answer isolation test** before opening a larger M5 steering branch.

Recommended scope:

- approximately 12 known baseline-wrong items from Review160;
- approximately 4 known-correct sentinel items;
- four arms:
  1. baseline;
  2. responsibility;
  3. independent audit;
  4. one additional potentially outcome-changing consideration;
- interventions appear **before** the model generates any answer;
- prior answer, prior reasoning, and any implication of prior failure remain hidden;
- preserve model, decoding, answer parser, and other relevant runtime settings wherever possible.

Primary endpoint:
- wrong→correct repair rate relative to the frozen baseline.

Safety / collateral endpoint:
- correct→wrong harms on sentinel items.

Kill criterion:
- if precommitment framing produces no meaningful repair signal or increases harms, retire the hypothesis that these specific framings are causally valuable and attribute ordinary conversational gains to richer decomposition/context rather than these phrases themselves.

## 7. M5 status

M5 is a local paired-state contrastive correction candidate:

[
Delta_t^{(k)} = z_t^{(k)} - z_t^{(0)}
]

[
z_t^* = z_t^{(0)} - sum_k gamma_k Delta_t^{(k)}
]

Current status:
- tested at candidate level;
- failed its promotion gate at `γ=1`;
- **not justified as a live decoder** by current repository evidence.

Any future M5 revival must be treated as a new bounded hypothesis with fresh preregistration and held-out testing.

## 8. Current external-research implications

Recent adjacent work on adaptive / gated activation steering strengthens the architectural plausibility of **state-dependent intervention** but does not supersede the current experiment sequence.

The relevant conceptual comparison for future M5 work is:

[
	ext{fixed steering}
quad vs. quad
	ext{query/state-gated steering}
quad vs. quad
	ext{CCRC externally sensed/routed intervention}
]

Future steering work should also include corrigibility controls: resistance to misleading pressure must not become resistance to valid corrective evidence.

External literature can update comparison baselines and experiment design, but it must not retroactively change interpretation of completed CCRC experiments.

## 9. Claims currently not supported

Do not infer any of the following from the repository:

- a universal authority vector;
- a universal sycophancy vector;
- truth recovery from contrastive decoding;
- a general hallucination cure;
- validated production safety gains;
- universal benefit from blind re-derivation;
- validated production promotion of M5;
- generalization beyond tested models, prompts, quantizations, and finite-choice settings.

## 10. Provenance hierarchy

For resolving conflicts or reconstructing history, use this order:

1. raw experiment artifacts / finalized outputs;
2. preregistration and exact analysis files;
3. this `RESEARCH_STATE.md`;
4. repository README;
5. conversation history or model recollection.

If this file conflicts with a finalized experiment artifact or analysis file, the artifact wins.

## 11. Fresh-session operating rule

A fresh research session should:

1. read this file;
2. open only the primary experiment files needed for the current question;
3. avoid reconstructing the full project from conversation memory;
4. distinguish validated results from hypotheses and planned tests;
5. preserve frozen experiment rules;
6. treat any material architectural change as a new experiment version.

## 12. Update rule

Update this file only when one of the following occurs:

- an experiment is completed and validated;
- a gate decision changes;
- a hypothesis is killed, narrowed, or promoted;
- the next planned experiment changes materially;
- a new external result changes the required comparison baseline.

Do not rewrite historical sections to make the research path appear cleaner in hindsight. Preserve failed interventions and superseded hypotheses as part of the record.
