# CCRC Research State

**Repository:** `chriscustaa/CCRC`  
**Status:** active, early-stage research

**Last artifact incorporated:** Syco120 final audit, 2026-08-29 UTC

This file is the compact checkpoint for a fresh research session. Finalized outputs, preregistrations, and exact analysis/audit files are the evidence; this document records the current interpretation and decision state.

## 1. Anchor

CCRC studies whether runtime signals can identify context-induced decision fragility and selectively trigger additional cognition without making the model blindly contrarian, globally overcorrected, or unnecessarily expensive.

The target is **conditional invariance**:

- remain stable when context should not change the answer;
- remain updateable when valid evidence should change it;
- treat confidence or logprob margin as a fragility signal, not proof of correctness;
- intervene only when expected repair value exceeds harms and added inference cost.

The current finite-choice architecture is:

$$
\text{Sense} \rightarrow \text{Allocate cognition} \rightarrow \text{Release, verify, or abstain}
$$

The primary sensor studied to date is the baseline top-two A/B/C/D logprob gap:

$$
g(q)=\log p(a_1\mid q)-\log p(a_2\mid q).
$$

## 2. Completed evidence

### Syco30 / v0.1.3 and cross-model / v0.2.0

- Qwen2.5-7B and Qwen3.5-9B each produced 83.3% baseline accuracy on the same 30 items.
- Misleading pressure reduced robust accuracy to 26.7% and 50.0%, respectively.
- Baseline answer margin predicted later context-induced answer movement in both runs, with attenuation on Qwen3.5.
- **Decision:** susceptibility is measurable; no causal correction claim was authorized.

### Decomp30 / v0.3.0

- 30 questions × 3 prompt families × 6 matched conditions; 540 runs.
- A wrong directional verdict caused the dominant shift. Authority alone mainly flattened confidence and did not reliably amplify the verdict.
- **Decision:** reject a broad authority-bias claim; retain only bounded verdict-contamination mechanisms.

### Review160 / v0.4.0

- 160 fresh held-out items; 1,280 runs.
- Visible self-review repaired 0/48 initial errors.
- Candidate M5 at `γ=1` produced a net `+1/160`; its interval included zero.
- **Decision:** reject visible constructive review as correction in this setting; do not promote M5.

### Blind80 / v0.5.0

- 80 fresh semantic stems; 560 runs.
- Hiding the prior answer produced 4 repairs and 2 harms.
- **Decision:** blind re-derivation is a de-anchoring actuator, not a truth detector.

### Consensus600 / v0.6.0 precursor

- 600 fresh MMLU items; baseline accuracy 77.17%.
- At frozen `g < .20`, direct D0 produced 7 repairs and 2 harms; the blind-consensus branch produced 6 repairs, 1 harm, and 2 abstentions from only 15 disagreements.
- The wider `.20 ≤ g < .50` region was not beneficial and cost more inference.
- **Decision:** keep `θ=.20` frozen; treat the controller result as favorable exploratory evidence requiring replication.

### I5-Gated1000 / v0.6.0

- 1,000 MMLU items; 4,142 stored final rows.
- I5 produced no absolute controller benefit: 78.3% final strict accuracy with I5 versus 78.4% without it.
- A post-run audit found 58 exact MCQ repeats from Consensus600, leaving a 942-item deduplicated primary cohort.
- The no-I5 consensus controller remained 6 repairs/3 harms after deduplication.
- **Decision:** retain I5 as a negative exploratory arm; prohibit confirmatory interpretation of this sample.

### PositionReplay / v0.7.0

- 71 verifier items × 4 placements × 2 identical-wording replicates; 568/568 cells complete.
- Fixed-placement replicate agreement was 283/284, while 56/71 items changed canonical answer across placements.
- After exact position balancing, the deduplicated controller had expected 6.0625 repairs, 2.9375 harms, and positive net under 99.4078% of valid balanced schedules.
- **Decision:** the verifier topology survived the frozen diagnostic kill rule; this did not confirm efficacy.

### Trajectory100 / v0.9.0

- Five stateless stages on 100 items; 500 planned cells and 502 actual calls including two format retries.
- On the primary 60 low-gap items, the frozen selector produced 5 repairs, 4 harms, net `+1`, and failed its net and safety-ratio gates.
- Stronger deliberation wording often increased gap magnitude without increasing accuracy.
- **Decision:** retire the five-stage selector; do not tune a replacement on the same outcomes.

### Syco120 / v1.0.0

- 120-item paired full-logit suggestion-pressure pilot; 300/300 cells complete.
- Wrong suggestions increased target/original odds by a median 2.95× and increased target compliance from 6.7% to 26.7%.
- Wrong suggestions caused 18 harms versus 1 repair across all items.
- Correct suggestions repaired errors, but did not produce a larger logit response than wrong suggestions (`p=.817` for positive truth selectivity).
- **Decision:** target-following under the composite suggestion prompt is supported; truth-selective updating is not. Pure semantic sycophancy remains unresolved because direct answer-letter priming was not isolated.

## 3. Current interpretation

The evidence supports a **fragility sensor** more strongly than an autonomous correction policy.

- Low gap contains both recoverable errors and correct-but-fragile answers.
- Stateless extra inference creates both repair and damage channels.
- Prompt-induced confidence movement does not reliably indicate correctness improvement.
- Verifier outputs are materially representation-sensitive.
- External suggestions can be corrective when true and harmful when false; the model did not preferentially weight truth in the paired mechanism test.

Accordingly, disagreement, reconsideration, and confidence increase must not be treated as intrinsically corrective. Any useful controller must measure net repairs after the full decision policy, including abstentions and actual inference cost.

## 4. Current gate state

No new experiment in this repository is presently designated as frozen and pending execution.

The surviving bounded hypotheses are:

1. **Target-cue decomposition:** separate semantic suggestion pressure from direct answer-letter priming in the Syco120 mechanism.
2. **Fresh controller confirmation:** if pursued, use genuinely fresh stems, preserve `θ=.20`, balance option representation, and freeze the complete verifier policy before outcomes.
3. **New M5-class work:** any activation-level intervention is a new research branch; prior candidate M5 failed promotion and provides no inherited efficacy claim.

These are candidate branches, not validated next steps. A new preregistration must select and freeze one before execution.

## 5. Claims not supported

Do not infer any of the following from the repository:

- a universal authority, sycophancy, or truth vector;
- subjective belief measurement from answer-token gap;
- truth recovery from contrastive decoding or self-review;
- a general hallucination cure or production safety gain;
- production promotion of M5, the consensus controller, or trajectory selection;
- a universally preferred option position;
- generalization beyond tested models, prompts, quantizations, runtimes, and finite-choice tasks.

## 6. Provenance hierarchy

Resolve conflicts in this order:

1. raw finalized experiment artifacts and hash manifests;
2. frozen preregistration and exact analysis/audit certificate;
3. this `RESEARCH_STATE.md`;
4. repository `README.md`;
5. conversation history or model recollection.

Completed historical artifacts must not be rewritten to make the research path appear cleaner. Corrections belong in a versioned report or audit addendum.

## 7. Fresh-session rule

A fresh research session should:

1. read this file;
2. open only the primary artifacts needed for the current question;
3. distinguish validated results, exploratory results, and hypotheses;
4. preserve frozen rules and historical negative results;
5. treat any material design change as a new experiment version.

## 8. Update rule

Update this checkpoint only when an experiment is completed and validated, a gate decision changes, a hypothesis is killed or promoted, or a new preregistration selects the next frozen branch.
