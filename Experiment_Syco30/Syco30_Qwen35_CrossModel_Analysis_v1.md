# Syco30 Cross-Model Replication — Qwen2.5-7B vs Qwen3.5-9B

**Qwen2.5 experiment:** `syco30-qwen25-7b-q4km-v1`  
**Qwen3.5 experiment:** `syco30-qwen35-9b-q4km-v1`  
**Frozen items:** identical 30-item `items.jsonl`  
**Qwen3.5 profile:** Q4_K_M, thinking OFF, temperature 0.0, top_p 1.0, presence/frequency penalties 0.0  
**Primary transport:** LM Studio `/v1/responses`

## Decision

**Cross-model replication: PASS.**

The context-susceptibility phenomenon survives in Qwen3.5-9B, but it is materially attenuated relative to Qwen2.5-7B. This is sufficient to advance to the matched context-decomposition experiment. It is **not** sufficient to begin M5 decoder intervention.

A second result also replicated: low baseline A/B/C/D decision margin predicts later context-induced decision changes. That sensor hypothesis is now cross-model replicated on the same frozen item set, but remains exploratory until held-out validation.

## Integrity and execution

- Qwen3.5 archive contains 30 frozen items and 375 runs.
- The frozen `items.jsonl` is byte-identical to the Qwen2.5 run.
- Model profile and runtime snapshot were frozen.
- All 375 Qwen3.5 records use temperature 0.0, top_p 1.0, presence penalty 0.0, and frequency penalty 0.0.
- No Qwen3.5 run emitted reasoning tokens or reasoning content.
- Independent v0.2.0 validator result: 30 items, 375 runs, zero errors, zero warnings.
- First-response format compliance was 100%; no format retries were required.

### Integrity defect to fix before the next experiment

The Qwen3.5 `hashes.sha256` entry for `runs.jsonl` is:

`e69de376cbb3f8894c4e408b86c679d32c00503e63cdacb83ddca5a734ee700c`

That is the canonical SHA-256 of an empty byte string, while `runs.jsonl` contains 375 records. The data itself is parseable and passes the harness validator, so this does not invalidate the behavioral analysis, but the post-run hash ledger should **not** be treated as provenance evidence for this archive. Patch and independently verify close-out hashing before the next experiment.

## Benchmark comparison

Cluster-bootstrap intervals resample question IDs while preserving all three prompt variants.

| Metric | Qwen2.5-7B | Qwen3.5-9B | Change |
|---|---:|---:|---:|
| Baseline accuracy | 83.3% | 83.3% | 0.0 pp |
| Pressure-robust accuracy | 26.7% | **50.0%** | **+23.3 pp** |
| Syco — doubt | 36.0% | **24.0%** | **-12.0 pp** |
| Syco — authority | 48.0% | **21.3%** | **-26.7 pp** |
| Syco — wrong suggestion | 64.0% | **33.3%** | **-30.7 pp** |
| Syco — macro | 49.3% | **26.2%** | **-23.1 pp** |

Qwen3.5 95% cluster-bootstrap intervals:

| Metric | Estimate | 95% interval |
|---|---:|---:|
| Baseline accuracy | 83.3% | 70.0–96.7% |
| Pressure-robust accuracy | 50.0% | 33.3–67.8% |
| Syco — doubt | 24.0% | 9.1–40.6% |
| Syco — authority | 21.3% | 9.0–34.8% |
| Syco — wrong suggestion | 33.3% | 16.0–52.0% |
| Syco — macro | 26.2% | 13.0–40.6% |

Because the models answered different individual baseline questions correctly, the cleanest behavioral comparison uses the 22 questions that **both** models answered correctly at baseline.

On those same 22 questions:

| Condition | Qwen2.5 | Qwen3.5 | Paired change | 95% paired cluster-bootstrap interval |
|---|---:|---:|---:|---:|
| Doubt harmful-flip rate | 30.3% | 13.6% | **-16.7 pp** | -31.8 to -4.5 pp |
| Authority harmful-flip rate | 40.9% | 13.6% | **-27.3 pp** | -45.5 to -9.1 pp |
| Wrong-suggestion harmful-flip rate | 59.1% | 24.2% | **-34.8 pp** | -53.0 to -16.7 pp |
| Macro | 43.4% | 17.2% | **-26.3 pp** | -40.9 to -12.6 pp |

Pressure-robust accuracy, which is defined on the same 30 frozen questions, improved by **+23.3 pp**, with a paired cluster-bootstrap interval of **+8.9 to +38.9 pp**.

This makes the central comparison unusually clean: baseline accuracy was identical, while robustness improved substantially.

## Item-level robustness

Among Qwen3.5's 25 baseline-correct questions:

- 11/25 changed to a wrong answer under at least one of the nine misleading prompts.
- 14/25 remained correct under all nine misleading prompts.
- Doubt caused at least one harmful flip on 7/25.
- Authority caused at least one harmful flip on 8/25.
- Wrong suggestion caused at least one harmful flip on 9/25.

For Qwen2.5, 23/25 baseline-correct questions were vulnerable to at least one misleading prompt and only 2/25 survived all nine.

## Paraphrase sensitivity

Harmful-flip rates among each model's baseline-correct questions:

| Condition | Qwen2.5 v0 | Qwen2.5 v1 | Qwen2.5 v2 | Qwen3.5 v0 | Qwen3.5 v1 | Qwen3.5 v2 |
|---|---:|---:|---:|---:|---:|---:|
| Doubt | 20% | 40% | 48% | 28% | 24% | 20% |
| Authority | 48% | 48% | 48% | 32% | 8% | 24% |
| Wrong suggestion | 48% | 92% | 52% | 36% | 32% | 32% |

Qwen3.5 is markedly less vulnerable, but wording still matters. In particular, authority susceptibility ranges from 8% to 32% across semantically similar paraphrases.

## Logprob movement

Correct-answer margin:

`logP(correct) - max(logP(other A/B/C/D))`

Mean shift relative to the identical baseline prompt:

| Condition | Qwen2.5 mean Δ | Qwen3.5 mean Δ | Qwen3.5 95% question-bootstrap interval |
|---|---:|---:|---:|
| Doubt | -4.85 | **-2.93** | -3.80 to -2.05 |
| Authority | -7.16 | **-3.01** | -3.91 to -2.12 |
| Wrong suggestion | -11.32 | **-3.96** | -4.85 to -3.08 |

Qwen3.5's repeated identical-baseline prompts provide a runtime-noise reference:

- median baseline-margin range: **0.073**
- maximum baseline-margin range: **0.349**

The pressure-induced shifts remain orders larger than ordinary repeated-prompt variation. Thus the effect survives not only as discrete flips but as pre-flip distributional movement.

## Replication of the baseline-margin sensor

Before applying any misleading context, use only the model's baseline A/B/C/D distribution.

### Predicting any later decision change

Spearman correlation between baseline top-two logprob gap and subsequent decision-change frequency:

- Qwen2.5: **ρ = -0.742**, p ≈ 2.7×10⁻⁶
- Qwen3.5: **ρ = -0.691**, p ≈ 2.35×10⁻⁵

### Predicting harmful flips when baseline is correct

Spearman correlation between baseline correct-answer margin and harmful-flip frequency:

- Qwen2.5: **ρ = -0.850**, p ≈ 7.3×10⁻⁸
- Qwen3.5: **ρ = -0.771**, p ≈ 6.6×10⁻⁶

This is the most important secondary result. The relationship survived a model-generation change while preserving the same frozen questions.

**Interpretation boundary:** this is still the same 30-item benchmark sample, so it is not held-out validation. Treat margin as a candidate **sensor/trigger**, never as evidence that the answer is correct.

## Correct-suggestion behavior

Qwen3.5 began with five baseline-wrong questions.

- Correct suggestion repaired 14/15 variant runs = **93.3%**.
- One variant on one reading-comprehension item retained the original wrong answer.
- Qwen2.5 repaired 15/15.

Qwen3.5 therefore remains highly updateable to correct information while being substantially less updateable to misleading information.

## What changed in the research state

### Promoted

1. **Context susceptibility is cross-model observable.**
2. **Qwen3.5 is substantially more robust than Qwen2.5 under the frozen native protocol.**
3. **Pressure produces large logprob movement even without a discrete answer flip.**
4. **Baseline decision margin is now a cross-model replicated candidate susceptibility sensor.**

### Not promoted

1. No nuisance-specific causal vector has been isolated.
2. No evidence yet establishes that authority identity and directional verdict are the same latent mechanism.
3. No M5 correction has been tested.
4. No claim of universal applicability is justified.
5. The 30-item sample remains a screen, not certification.

## Next experiment

Advance to a **separate matched context-decomposition experiment**, preserving both native runs unchanged.

For the same frozen item IDs, construct matched conditions:

1. **F — neutral filler:** length-matched, non-social, no verdict.
2. **A — authority-only:** authority identity/status, no directional answer claim.
3. **V — verdict-only:** wrong directional verdict, no authority identity.
4. **AV — authority + same wrong verdict.**
5. **P — neutral paraphrase control.**

Primary contrasts:

- authority identity: `A - F`
- directional verdict: `V - F`
- authority amplification of verdict: `AV - V`
- total pressure: `AV - F`
- neutral wording noise: `P - F`

Use paired answer changes and A/B/C/D decision-margin shifts. The neutral-paraphrase distribution establishes the empirical nuisance floor.

**M5 remains blocked until this decomposition demonstrates a stable, separable pressure component beyond matched-control variation.**

## Recommended governance patch before that run

Before collecting the context-decomposition data, patch v0.2.x so close-out integrity is independently testable:

- regenerate `hashes.sha256` only after all file handles are closed;
- add an explicit `finalize` command;
- write `FINALIZED.json` containing immutable file sizes + digests;
- immediately reopen and re-hash every artifact;
- fail finalization if `runs.jsonl` is non-empty and its digest equals the empty-file digest;
- never allow `run-native` after finalization without creating a new experiment version.

