# CCRC 568-cell position-balanced replay

This package runs and audits the frozen verifier replay described in `PREREGISTRATION.md`. The uploaded I5-1000 result bundle has already been converted into self-contained, hash-pinned frozen inputs. The source outcome bundle is not required to execute the replay.

## What is frozen

- 71 replay items;
- four item-specific Williams-square placements per item;
- identical wording for R1 and R2;
- two frozen seed streams;
- 568-cell call order;
- B0/D0 outcomes and θ=.20 gate membership;
- deduplicated 942-item primary cohort;
- exact balanced-schedule enumeration;
- kill rule: expected net must be positive and at least 95% of valid balanced schedules must have positive net;
- no aggregation across all eight cells.

## Setup

Use Python 3.10 or newer. In LM Studio, load the exact `qwen/qwen3.5-9b` Q4_K_M runtime used by I5-1000 with thinking off. The example config already freezes that model key and the audited runtime snapshot hash.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
```

## Safe execution sequence

```bash
python -m harness.cli doctor \
  --config config.json \
  --out doctor.json

python -m harness.cli init \
  --config config.json \
  --doctor doctor.json \
  --out experiment_position_replay

python -m harness.cli transport-check \
  --config config.json \
  --out experiment_position_replay

python -m harness.cli run \
  --config config.json \
  --out experiment_position_replay \
  --limit 8

python -m harness.cli validate \
  --out experiment_position_replay
```

Inspect the eight acceptance cells. They remain part of the final run; do not delete or rerun them. Resume the remaining 560 cells:

```bash
python -m harness.cli run \
  --config config.json \
  --out experiment_position_replay

python -m harness.cli finalize \
  --config config.json \
  --out experiment_position_replay
```

The runner is resumable by frozen `run_key`. `finalize` requires all 568 cells to validate and writes `analysis.json`, `cell_results.csv`, `validation.json`, `FINALIZED.json`, and a SHA-256 manifest.

## Reading the result

The authoritative decision is `analysis.json → primary_decision`.

- `actuator_survives: true` means the topology may proceed to one new powered confirmatory sample. It does not confirm efficacy.
- `actuator_survives: false` means retire the current verifier actuator. Do not tune θ or reinterpret an eight-cell aggregate as a controller.

## Integrity checks

Run the offline test suite before connecting to LM Studio:

```bash
python tools/run_offline_tests.py
# Or, after installing development dependencies: pytest -q
python -m harness.cli validate --out experiment_position_replay
```

The `frozen/FROZEN_SHA256.txt` manifest protects the dataset, policy backbone, evidence-stem union, call plan, and provenance record.
