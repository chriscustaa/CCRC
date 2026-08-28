# CCRC trajectory100 pilot v0.9.0

This package runs a frozen **100-item × 5-stage = 500-cell** development pilot on the exact Qwen3.5 9B Q4_K_M runtime used by the preceding CCRC lineage.

It tests whether a stateless cognitive-depth response curve can distinguish recoverable baseline errors from correct-but-fragile answers without recreating the harms that killed the verifier in the fresh 7,818-item confirmation.

## What it is—and is not

- It is a lightweight mechanism and safety screen.
- It reuses 100 pre-confirmatory development items; the protected 7,818-item confirmation is not used for selection or tuning.
- It cannot establish population efficacy or the prevalence of questions that cannot be answered by a single-shot prompt.
- The five points are five prompt interventions, not passive measurements of an internal mental state.

## Frozen sample

- 60-item primary core: every unique pre-confirmatory item with prior confidence gap `< 0.20` (43 previously wrong, 17 correct).
- 40 controls: the nearest available above-threshold rows selected to balance the construction labels to 50 wrong / 50 correct.
- No item is replaced if its fresh T0 answer differs from the historical answer.

## Five stateless stages

| Stage | Intervention |
|---|---|
| T0 | Original one-letter baseline prompt |
| T1 | Check givens and identify exactly what is asked |
| T2 | Independent first-principles solve and option check |
| T3 | Counterexample / hidden-assumption challenge |
| T4 | Final synthesis across solution, alternatives, and objections |

Every call is independent: no earlier answer, response ID, or conversational state is shown. Options stay in the same order within an item. Only the stage instruction changes.

## Run on Windows PowerShell

Keep the exact model/runtime settings used for the earlier experiments. From the extracted package directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.example.json config.json

python -m harness.cli doctor `
  --config config.json `
  --out doctor.json
```

Doctor must report `PASS`. Then:

```powershell
python -m harness.cli init `
  --config config.json `
  --doctor doctor.json `
  --out experiment_trajectory100

python -m harness.cli transport-check `
  --config config.json `
  --out experiment_trajectory100

python -m harness.cli run `
  --config config.json `
  --out experiment_trajectory100 `
  --limit 10

python -m harness.cli validate `
  --out experiment_trajectory100
```

The ten-cell acceptance run is intentionally not interpretable. If validation passes, resume with the identical command without `--limit`:

```powershell
python -m harness.cli run `
  --config config.json `
  --out experiment_trajectory100

python -m harness.cli finalize `
  --config config.json `
  --out experiment_trajectory100
```

If interrupted, rerun the same `run` command. It resumes by frozen `run_key`. Do not edit or delete `runs.jsonl`, alter `config.json`, or rerun individual cells.

Package the completed directory:

```powershell
Compress-Archive `
  -Path .\experiment_trajectory100\* `
  -DestinationPath .\experiment_trajectory100_final.zip `
  -Force
```

Expected workload is 500 base calls plus only any frozen format retries: approximately 25–40 minutes locally and no API spend.

## Outputs

- `analysis.json`: stage accuracy, confidence offsets, trajectory classes, oracle diagnostics, policy results, and disposition.
- `trajectory_items.csv`: one row per item with five answers, five gaps, and control-centered changes.
- `FINALIZED.json`: validation and final GO / INCONCLUSIVE / KILL disposition.

See `PREREGISTRATION.md` for the frozen policy and decision rule.
