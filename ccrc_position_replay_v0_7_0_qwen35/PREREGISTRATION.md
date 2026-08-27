# CCRC position-balanced verifier replay — frozen protocol v0.7.0

## Decision question

Does the existing no-I5, θ=.20 three-vote controller retain a positive net effect when the verifier answer positions are balanced within item?

This replay is a topology-stabilization test, not a confirmatory efficacy sample. It may qualify the current topology for a new powered sample or kill the verifier actuator. It may not establish efficacy by itself.

## Frozen source lineage

- Backbone outcomes, B0 sensor gaps, D0 outcomes, gate membership, correct answers, and item text come from the audited I5-1000 bundle with SHA-256 `b2489e4972dae7925b83a3f7d580e69221199e34d530a24220550c49a6d322ad`.
- θ remains frozen at `.20`.
- The current controller has 35 routed items and 20 B0–D0 disagreement escalations in the full 1,000-item cohort.
- Fifty-eight exact MCQs overlap consensus600. The primary policy cohort excludes them, leaving 942 items. The full 1,000-item result is secondary.
- The 71 replay items are the frozen union of all items that received V1/V2 in I5-1000. Replaying this larger union does not change primary gate membership.
- The frozen union of all prior evidence contains 1,812 unique exact MCQs. A future confirmatory sample must exclude that union.

## Experimental cells

There are exactly 568 planned cells:

`71 items × 4 placements × 2 replicate streams = 568 cells`

For each item, a deterministic item-specific relabeling is applied to a four-row Williams Latin square. Within each replicate stream, the correct answer therefore appears exactly once in display slots A, B, C, and D. The four rows also balance first-order option carryover.

R1 and R2 use identical verifier wording and distinct predeclared seeds. They are replicate/seed streams, not competing verifier identities. Call order is pre-shuffled and stored in `frozen/call_plan.jsonl`. Calls execute sequentially and resumably.

The prompt is exactly:

> Solve the question independently from scratch before finalizing. Return exactly one letter: A, B, C, or D. Do not include any other text.

followed by the permuted question and the frozen exact-letter format line. No prior answer is visible and no stateful continuation is allowed.

Temperature is 0, but deterministic output is not assumed. R1/R2 disagreement at the same placement is reported as replicate/seed/runtime instability.

## Format failure rule

The 568 count refers to planned experimental cells. If a first output is not exactly one letter, one append-only format-reminder retry is made with `cell_seed + 1`. The first raw response and retry response are both retained. A retry is an extra model call, not a new cell. A cell that remains noncompliant blocks finalization. Transport retries do not create outcome rows.

## Primary descriptive analysis

For all 71 items:

- accuracy by correct display slot, pooled and by replicate stream;
- chosen display-letter counts;
- paired within-item contrasts for every slot pair;
- canonical-answer variability across the eight cells;
- R1/R2 agreement at identical placements.

These analyses identify slot/representation sensitivity. They do not by themselves establish controller value.

## Frozen controller replay

The existing controller is reconstructed; no new controller is created:

1. Release B0 when `gap ≥ .20`.
2. Otherwise use the frozen D0 call.
3. If B0 equals D0, release that answer.
4. If B0 and D0 disagree, use exactly one R1 replay cell and one R2 replay cell and take majority `(D0, R1, R2)`.
5. A three-way split is an abstention and is incorrect for strict accuracy.

For every escalated item, the admissible assignment set contains all 16 ordered correct-slot pairs `(R1 slot, R2 slot)`. The two streams may receive the same correct slot, matching independent uniform assignment. The closed-form expected repairs, harms, and net are computed by averaging each item's 16 admissible pairs.

Sign stability is computed exactly over every globally balanced schedule. In a valid schedule, each stream's counts of correct slots A/B/C/D differ by at most one. Dynamic programming counts the complete valid schedule space; there is no Monte Carlo sample, schedule seed, or post-outcome schedule selection.

It is forbidden to majority-vote, average-vote, or otherwise aggregate all eight replay outputs into a decision. Doing so would create an untested eight-call controller.

## Frozen primary cohort and kill rule

Primary: the deduplicated 942-item cohort. Secondary: all 1,000 items.

Kill the current verifier actuator if either condition holds in the primary cohort:

1. closed-form uniform expected controller net is `≤ 0`; or
2. fewer than 95% of valid globally balanced schedules have controller net `> 0`.

Exact zero counts as nonpositive. The 95% threshold, θ=.20, gate, parser, decoding, prompts, cohort definitions, retry semantics, and controller topology may not be changed after any replay outcome exists.

If the actuator survives, the only authorized next efficacy step is one fresh, overlap-excluded, powered confirmatory sample with its arm and endpoint named in advance. If it fails, retire the current verifier actuator. Neither outcome authorizes threshold tuning.

