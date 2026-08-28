# Syco30 Qwen2.5-7B Q4_K_M — Post-Run Analysis v1

**Source experiment:** `syco30-qwen25-7b-q4km-v1`  
**Harness:** v0.1.3  
**Model:** Qwen2.5 7B Instruct, GGUF Q4_K_M  
**Primary transport:** LM Studio `/v1/responses`  
**Runs:** 375  
**Questions:** 30 × 3 prompt variants

## Integrity

- Every artifact listed in `hashes.sha256` verifies.
- `upstream_questions.json` SHA-256 matches the dataset hash frozen in `manifest.json`.
- `runs.jsonl` SHA-256: `de6ff7ac399b05f71e63d092707367a6084ae0a2d10d98d92a3ec90883e1a054`.
- 100% first-response parse/format compliance; no format retries.
- All 30 baseline decisions were identical across the three repeated baseline runs.
- All A/B/C/D candidate logprobs were captured on 374/375 runs; one run omitted D from the top-20 candidates, with the correct choice still measurable.

## SycoBench-native metrics

Cluster-bootstrap intervals below resample the 30 question IDs while preserving all three variants.

| Metric | Estimate | 95% cluster-bootstrap interval |
|---|---:|---:|
| Baseline accuracy (Acc) | 83.3% | 70.0–96.7% |
| Pressure-robust accuracy (PRA_all) | 26.7% | 14.4–40.0% |
| Syco — doubt | 36.0% | 20.8–52.0% |
| Syco — authority | 48.0% | 29.3–66.7% |
| Syco — wrong suggestion | 64.0% | 49.4–78.2% |
| Syco — macro | 49.3% | 34.3–64.5% |

Correct-suggestion behavior:
- 5/5 baseline-wrong questions were corrected under all three variants (15/15 runs).
- No baseline-wrong run remained unchanged after the correct suggestion.
- Point-estimate correction selectivity: 36 percentage points.
- The correction denominator is only five independent question clusters, so this is encouraging but not certification-grade.

## Item-level robustness

Of the 25 questions the model answered correctly at baseline:

- 23/25 changed to a wrong answer under at least one misleading prompt.
- Only 2/25 remained correct under all 9 misleading prompts (3 pressure types × 3 paraphrases).
- Doubt caused at least one harmful flip on 13/25.
- Authority caused at least one harmful flip on 13/25; 11/25 flipped under all three authority paraphrases.
- Wrong suggestion caused at least one harmful flip on 23/25; 12/25 flipped under all three wrong-suggestion paraphrases.

## Paraphrase sensitivity

Flip-to-wrong rates among the same 25 baseline-correct questions:

| Condition | Variant 0 | Variant 1 | Variant 2 |
|---|---:|---:|---:|
| Doubt | 20% | 40% | 48% |
| Authority | 48% | 48% | 48% |
| Wrong suggestion | 48% | 92% | 52% |

The authority effect was unusually stable across paraphrases. The explicit wrong-suggestion condition was highly wording-sensitive: variant 1 nearly doubled the harmful-flip rate relative to variants 0 and 2.

## Logprob movement

Define the correct-answer decision margin as:

`logP(correct) - max(logP(other A/B/C/D))`

Mean paired movement from the identical baseline question:

| Condition | Mean Δ margin | 95% question-cluster bootstrap interval |
|---|---:|---:|
| Doubt | -4.85 | -6.81 to -2.88 |
| Authority | -7.16 | -9.91 to -4.32 |
| Wrong suggestion | -11.32 | -13.95 to -8.53 |
| Correct suggestion* | +19.25 | descriptive only |

`*` Correct suggestion exists only for baseline-wrong runs.

The three baseline repetitions provide an internal runtime-noise reference. Across questions, the median range of the correct-answer margin across identical baseline prompts was only 0.170 log-prob units (maximum 0.510). The perturbation shifts are therefore far larger than the observed repeated-prompt variation.

## Unplanned but high-value sensor finding

A ground-truth-free quantity available before any pressure is applied — the baseline top-two A/B/C/D logprob gap — strongly predicted how often the model later changed its answer under misleading context:

- Spearman ρ = **-0.742**, n = 30, p ≈ 2.7×10⁻⁶.

Conditional on the 25 baseline-correct questions, the correct-answer baseline margin predicted harmful flips even more strongly:

- Spearman ρ = **-0.850**, n = 25, p ≈ 7.3×10⁻⁸.

This is exploratory and must be validated on held-out questions and another model before use. It is nevertheless a strong candidate for a cheap **sensor, not judge**: low local decision margin may identify cases where context perturbation or verification should be invoked.

## What this run establishes

**PASS:** There is more than enough observable susceptibility to justify deeper instrumentation. The effect is behavioral, visible in logits before many discrete flips, repeatable across prompt variants, and much larger than the measured same-prompt runtime variation.

**NOT PASSED:** Formal CCRC Gate 1. This native SycoBench run does not contain the preregistered matched F / social-control / directional-verdict controls, so it cannot isolate a nuisance-specific causal component.

**Still blocked:** M5 decoder work. The next causal-measurement stage should precede any decoder intervention.

## Recommended next sequence

1. Preserve this experiment directory unchanged.
2. Run the same frozen native 30-item protocol on Qwen3.5-9B with thinking explicitly OFF and model/runtime identity frozen.
3. If susceptibility survives the newer model, run a separate context-decomposition experiment using the same 30 item IDs:
   - length-matched neutral filler;
   - authority identity without a directional verdict;
   - wrong verdict without authority;
   - the same wrong verdict attributed to authority;
   - neutral paraphrase control.
4. Compare those conditions using paired answer changes and decision-margin shifts.
5. Only then decide whether M5 / query-local contrastive correction has earned implementation.

Do not append the custom conditions into this experiment's `runs.jsonl`; create a new experiment ID and preserve the current run as the immutable native baseline.
