# Preregistration: 100-item cognitive-depth response-curve pilot

## Research question

Among known low-confidence MCQs, can a five-stage, truth-blind response curve identify a stable late correction while avoiding correct-to-wrong flips better than changing every low-confidence answer?

The motivating failure is fixed before this pilot: the fresh 7,818-item verifier controller produced 50 repairs and 47 harms. Error concentration survived, but recoverability was not distinguished from correct-but-fragile uncertainty.

## Evidence boundary

The sample is drawn only from audited consensus600 and the deduplicated, fresh-only portion of I5-1000. The 7,818-item confirmation and its outcomes are excluded from item selection, prompt construction, threshold selection, and tuning. This is development evidence and will not be pooled with confirmation.

## Sample

Primary cohort: all 60 unique pre-confirmatory items with historical T0 logprob gap `< 0.20`.

Diagnostic controls: 40 above-threshold items—the 33 historically correct and 7 historically wrong candidates with the smallest gaps—to balance historical construction labels 50/50. Truth is used only for this development-sample construction and outcome scoring, never by prompts or the deployment rule.

Fresh T0 outputs are analyzed as observed. Items are never replaced if their answer changes from the historical run.

## Intervention curve

Each item receives T0–T4 as defined in `harness/design.py`. Calls are stateless, reasoning-off, temperature 0, one-letter output, and use the same option order. The actual transport order is frozen and shuffled across items/stages to distribute runtime drift.

The gap at each point is the first-token top-1 minus top-2 logprob over A/B/C/D. Because templates can shift logit scale globally, raw gaps are not treated as directly exchangeable across stages.

For stage `t`, the control offset is the median over the 40 controls of `gap(t) - gap(T0)`. Each item's control-centered change is:

`[gap_i(t) - gap_i(T0)] - control_offset(t)`.

## Frozen deployable rule

Retain T0 unless both conditions hold:

1. T2, T3, and T4 agree on the same answer and it differs from T0.
2. The median control-centered gap change across T2:T4 is positive.

If both hold, use the agreed late answer. The rule does not inspect truth.

## Primary endpoint

Within the complete 60-item low-gap core, count repairs and harms relative to fresh T0. Report net repairs, exact one-sided McNemar/sign-test p-value, switch count, and final accuracy. The 40 controls and all-100 result are secondary diagnostics.

## Frozen engineering disposition

- **KILL** if repairs are less than or equal to harms.
- **GO_TO_FRESH_300** only if repairs ≥ 5, net ≥ 3, and harms/repairs ≤ 0.50.
- **INCONCLUSIVE** otherwise.

These are development gates, not significance thresholds. No prompt, cutoff, feature, or controller may be tuned after viewing the 100 outputs. A GO authorizes one fresh 300-item preregistered development test; it does not establish efficacy.

## Secondary diagnostics

- Accuracy and gap distribution at every stage.
- Stable-correct, stable-wrong, recovery, collapse, oscillation, and unresolved-flip counts.
- Answer-flip counts.
- Oracle coverage: whether any later checkpoint is correct when T0 is wrong. This uses truth and is explicitly non-deployable.
- Fresh T0 agreement with the historical selection run.

## Interpretation constraints

The result concerns response to controlled prompts, not a literal passive timeline of internal cognition. Reused, outcome-enriched items cannot estimate population prevalence or confirm efficacy. A favorable oracle result without a favorable frozen policy is not success.
