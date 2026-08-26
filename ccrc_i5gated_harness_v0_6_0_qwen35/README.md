# CCRC I5 × Sensor-Gated Blind Verifier Harness v0.6.0

Reproducible next-step CCRC experiment testing whether the five-principle **I5** instruction layer changes correctness by itself and in combination with the Blind80-promoted sensor-gated blind re-derivation controller.

## What this adds

- 2×2 paired design: routing OFF/ON × I5 OFF/ON.
- New 1,000-item subject-balanced MMLU holdout, dataset revision pinned.
- Frozen θ=.20 primary threshold and θ=.50 comparator.
- Blind D0/D5 branches with no baseline answer exposure.
- Neutral V1/V2 verifier calls: no I5, no B/D output, deterministic distinct option permutations.
- Majority vote `{D,V1,V2}` with baseline excluded; no majority → abstain.
- Exact McNemar + deterministic paired bootstrap analysis.
- Repairs/harms, interaction effect, coverage/selective accuracy, and verifier diagnostics.
- Separate actual experimental call count from production-equivalent controller calls.
- Strict runtime snapshot and reasoning-OFF checks inherited from Blind80.

## Integrity boundary

Read `PREREGISTRATION.md` before running. Once the first model output is appended to `runs.jsonl`, I5 wording, θ values, dataset selection, and primary metrics are frozen. Changes require a new experiment version.

MMLU is source-new relative to the prior CCRC SycoBench series, not guaranteed pretraining-unseen.

## Setup

```bash
cd ccrc_i5gated_harness_v0_6_0_qwen35
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
cp config.example.json config.json
```

Set `model_id` in `config.json` to the exact loaded LM Studio model key. Do not alter the required runtime snapshot unless intentionally starting a new runtime replication.

## Run order

```bash
mkdir -p experiment_i5gated1000

python -m harness.cli doctor \
  --config config.json \
  --out experiment_i5gated1000/doctor.json

python -m harness.cli transport-check \
  --config config.json \
  --out experiment_i5gated1000/transport_check.json

python -m harness.cli prepare \
  --config config.json \
  --experiment-dir experiment_i5gated1000

# Full resumable run. Existing run_keys are skipped.
# `--limit N` exists for operational debugging, but the first study response
# freezes the design; do not inspect a partial result and then modify v0.6.0.
python -m harness.cli run \
  --config config.json \
  --experiment-dir experiment_i5gated1000

python -m harness.cli summarize \
  --config config.json \
  --experiment-dir experiment_i5gated1000

python -m harness.cli validate \
  --config config.json \
  --experiment-dir experiment_i5gated1000

python -m harness.cli finalize \
  --config config.json \
  --experiment-dir experiment_i5gated1000
```

Run unit tests before inference:

```bash
pytest -q
```

## Generated experiment artifacts

- `doctor.json` — strict model/runtime preflight.
- `transport_check.json` — Responses/logprob/reasoning-OFF transport check.
- `items.jsonl` — frozen selected holdout.
- `manifest.json` — dataset revision, item hash, I5 hash, thresholds, runtime snapshot requirement.
- `prompt_audit.json` — frozen I5 and blindness invariants.
- `runs.jsonl` — resumable per-condition records.
- `summary.json` — 2×2 effects, controller metrics, interaction, verifier diagnostics.
- `validation.json` — contamination/completeness/runtime checks.
- `hashes.sha256` — experiment artifact hash ledger.
- `FINALIZED.json` — emitted only after validation PASS.

## Reading the result

The first line of inquiry is **not** whether I5 makes answers sound better. It is whether `B5-B0` produces more wrong→right flips than right→wrong flips. The second is whether the θ=.20 controller adds value independently of I5. The third is the interaction: whether I5 improves or degrades the controller beyond its direct effect.

A positive θ=.50 result does not authorize threshold migration from .20; it is a frozen comparator and would require a subsequent preregistered experiment for promotion.
