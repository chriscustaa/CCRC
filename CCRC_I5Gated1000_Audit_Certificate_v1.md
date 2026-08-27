# CCRC I5-Gated-1,000 Audit Certificate v1

**Audit date:** 2026-08-26  
**Artifact:** `experiment_i5gated1000(1).zip`  
**Experiment ID:** `ccrc-i5gated1000-qwen35-9b-q4km-v1`  
**Outer ZIP SHA-256:** `b2489e4972dae7925b83a3f7d580e69221199e34d530a24220550c49a6d322ad`

## Verdict

**CONDITIONAL PASS for exploratory mechanism analysis and the balanced verifier replay. NOT PASS as a wholly fresh or confirmatory sample.**

The archive is internally intact and every load-bearing point estimate reconstructs from raw records. The principal defect is sample reuse: **58/1,000 complete MCQs are exact repeats from consensus600**. This does not alter the I5-OFF θ=.20 consensus-controller result after deduplication, but it invalidates the “1,000 fresh stems” description and changes the direct-D0 pooled ledger.

**Execution decision:** the position-balanced replay may proceed after its pre-registration is amended to report a 942-item deduplicated primary analysis and the original 1,000-item result as sensitivity. No confirmatory sample or efficacy claim is authorized yet.

## 1. Artifact and raw reconstruction — PASS

- ZIP decompression and CRC test: PASS.
- All nine files covered by `hashes.sha256`: PASS.
- Finalized item, run, and summary hashes: PASS.
- Items: 1,000 unique question IDs, source IDs, and semantic-stem hashes.
- Run rows: 4,142 unique keys: B0=1,000, B5=1,000, D0=1,000, D5=1,000, V1=71, V2=71.
- Reported calls: 4,160 = 4,142 stored final rows + 18 recorded retry calls.
- Runtime snapshot hash is identical across every run.
- Sensor gaps, canonical/display answer mappings, verifier selection, routing, majority decisions, abstentions, repairs, harms, and strict accuracies all reconstruct exactly.
- No prior answer, stateful continuation, detected reasoning, or I5 instruction leaked into verifier prompts.

### Recomputed core results

| Condition | Correct / 1,000 | Accuracy | Retries |
|---|---:|---:|---:|
| B0 | 781 | 78.1% | 0 |
| B5 | 777 | 77.7% | 0 |
| D0 | 784 | 78.4% | 18 |
| D5 | 778 | 77.8% | 0 |

### Recomputed θ=.20 results

| Arm | Routed | Gate errors | Repairs | Harms | Net | Final strict correct |
|---|---:|---:|---:|---:|---:|---:|
| I5-OFF direct D0 | 35 | 25 | 8 | 6 | +2 | — |
| I5-OFF consensus controller | 35 | 25 | 6 | 3 | +3 | 784 |
| I5-ON direct D5 | 39 | 28 | 8 | 4 | +4 | — |
| I5-ON consensus controller | 39 | 28 | 9 | 3 | +6 | 783 |

The I5-ON controller's larger within-arm net does **not** mean I5 improved the system: it starts from a worse B5 baseline. Absolute strict accuracy is 783/1,000 with I5 versus 784/1,000 without it.

## 2. Cross-experiment sample overlap — MATERIAL DEFECT

The I5 items were compared against the original item files from decomp30, review160, blind80, and consensus600: 870 prior MCQs total and 870 unique normalized stems.

- **58 exact full-MCQ duplicates** were found, all from consensus600.
- 2/35 I5-OFF θ=.20 routed items are duplicates.
- 4/71 verifier-stage items are duplicates.
- One duplicate is a direct-D0 repair in both consensus600 and I5-1,000.
- The duplicate items contribute **zero repairs and zero harms** to the I5-OFF θ=.20 consensus controller.

### Deduplicated sensitivity

| Quantity | Original | Excluding 58 repeats |
|---|---:|---:|
| Analysis sample | 1,000 | 942 |
| I5-OFF θ=.20 gate | 35 | 33 |
| Errors inside gate | 25 | 23 |
| Direct D0 repairs / harms | 8 / 6 | **7 / 6** |
| Consensus-controller repairs / harms | 6 / 3 | **6 / 3** |
| Verifier items | 71 | 67 |
| V1 correct | 33 | 30 |
| V2 correct | 42 | 41 |

### Ledger amendment

- Consensus-controller exploratory pool remains numerically **12 repairs / 4 harms**, one-sided exact p≈.038, because repeated items contribute no controller events. It remains post hoc and verifier-confounded.
- Direct-D0 exploratory pool must change from **15/8 to 14/8**, one-sided exact p≈.143, after removing the repair duplicated across both experiments.
- The within-gate density evidence is **23/33 fresh-only**, not 25/35 wholly independent.

No pooled result becomes confirmatory.

## 3. I5 intervention classification — PROMPT-LEVEL; NO BENEFIT DETECTED

I5 is a system-prompt treatment applied only to B5 and D5. It does not modify logits, decoding, model weights, routing thresholds, or verifier decisions. It is therefore **not M5-class or decoder-adjacent**.

The conversation record supports user authorization to test the five custom-instruction principles, but that authorization and its stage-boundary classification are absent from the bundle. Record this certificate as the external authorization/classification addendum; do not rewrite the original ZIP.

Observed I5 effects are nonpositive:

- B5−B0: 21 repairs, 25 harms, net −4.
- D5−D0: 28 repairs, 34 harms, net −6.
- θ=.20 final controller accuracy: I5-ON 78.3% versus I5-OFF 78.4%.

**Decision:** retain I5 as a completed negative exploratory arm; do not carry it into the verifier topology or confirmatory design.

## 4. Verifier/position evidence — REPLAY WARRANTED

The 71 verifier items reconstruct as follows:

- V1: 33/71 correct.
- V2: 42/71 correct.
- Canonical answer agreement: 40/71; disagreement: 31/71.
- V1 and V2 use the same verifier wording. Their only designed differences are permutation/seed/call assignment, so “verifier identity” is not a semantic treatment in this bundle.

Correct-answer slots were already close to balanced when pooled: A=36, B=37, C=36, D=33. Despite that, displayed C was selected 56/142 times (39.4%), and accuracy by correct slot was A=50.0%, B=32.4%, C=72.2%, D=57.6%. This independently supports a material permutation/position effect, but does not identify its causal decomposition; the balanced within-item replay remains necessary.

The V1/V2 accuracy difference is not explained by simple marginal correct-slot counts. Full permutation interactions, seed/call effects, and residual nondeterminism remain live possibilities.

## 5. Provenance limitations — RECORDED, NOT FATAL FOR REPLAY

1. `preregistered_before_outcomes: true` is internally chronological but not externally anchored; no complete frozen pre-registration is included.
2. Dataset revision, quotas, and selected-item hash are recorded, but the selection seed/algorithm and source dataset bytes are absent, so the 1,000-item draw is not independently regenerable from this bundle alone.
3. The 18 retry rows contain the final retry prompt/output and call-count metadata, but not the first failed raw outputs. Final decisions reconstruct; retry causation does not.
4. Model name, quantization, size, runtime configuration, and snapshot hash are consistent, but no GGUF binary SHA-256 is recorded. Exact model-byte identity is therefore not certified.
5. Bootstrap intervals in `summary.json` lack a bundled implementation/seed. Their point estimates match the raw data; exact interval reproduction was not certified.

These limitations prohibit treating I5-1,000 as confirmatory evidence. They do not prevent a diagnostic replay whose new cells, assignment space, retry rules, and estimator are frozen before execution.

## 6. Authorized next experiment gate

Before running the 568 verifier calls, freeze these amendments:

1. Run all 71 items × four Latin-square placements × two verifier replicates so the mechanism map remains complete.
2. Primary policy analysis: exclude the 58 consensus600 duplicates from the 1,000-item controller cohort, leaving 942 items and 67 verifier-union items. Report the full 1,000 secondarily.
3. Reconstruct the existing three-vote controller over the predeclared balanced V1/V2 assignment space. Never majority-vote across all eight replay outputs.
4. Kill the verifier actuator if the closed-form balanced expected net is ≤0 or fewer than 95% of valid balanced schedules yield net >0; zero is nonpositive.
5. Treat temperature 0 outputs as recorded observations, not guaranteed deterministic functions. Log duplicate-cell disagreement.
6. Future confirmatory sampling must exclude the union of all prior semantic-stem hashes. Across these five bundles, that union currently contains **1,812 unique MCQs**.

## State

- **Anchor:** θ=.20 frozen; verifier stabilization precedes confirmation.
- **Last validated:** I5 raw metrics reconstruct; sample overlap identified and deduplicated; I5 is prompt-level and nonbeneficial.
- **Open risks:** position/permutation causality, incomplete model-byte provenance, unanchored pre-registration.
- **Pending test:** amended 568-call balanced replay.
- **Kill:** verifier actuator fails under the balanced expectation/stability rules above; no threshold tuning under any outcome.

