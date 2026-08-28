# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

CCRC (Causal Contrastive Reasoning Control) is an experimental research repository, not a product
codebase. It studies whether runtime signals (answer log-probability margins) can detect
context-induced decision fragility in an LLM and selectively trigger extra cognition (blind
re-derivation, blind verification) — without becoming globally contrarian or blindly expensive.
The target property is *conditional invariance*: stay stable when context shouldn't change the
answer, stay updateable when it should.

Read `RESEARCH_STATE.md` at the repo root before doing any research work here — it is the
authoritative, compact checkpoint of validated findings, the current controller hypothesis, and
the next planned test (see its own "Fresh-session operating rule" and "Provenance hierarchy"
sections). Note it can lag the newest `Experiment_*` directories (e.g. Consensus600,
PositionReplay) if it hasn't been updated since their audit certs landed — check directory
mtimes/git log if the two disagree, and prefer the primary experiment artifacts.

Each experiment's own analysis/audit `.md` file is the primary evidence for that experiment; use
`RESEARCH_STATE.md` for the cross-experiment narrative and current status only.

## Repository layout

Each `Experiment_<Name>/` directory is one self-contained research iteration:

```
Experiment_<Name>/
  <Analysis|Audit>_*.md          # human-readable findings + gate decision (start here for evidence)
  ccrc_<name>_harness_v<ver>/    # the exact harness code + frozen inputs used for that run
  ccrc_<name>_harness_v<ver>.zip # archived snapshot of the same package, for provenance/hashing
```

Chronological order (oldest → newest): `Experiment_Syco30` → `Experiment_Decomp30` →
`Experiment_Review160` → `Experiment_Blind80` → `Experiment_I5Gated1000` →
`Experiment_Concensus600` → `Experiment_PositionReplay`. Later experiments build on frozen
outcomes/items from earlier ones (e.g. PositionReplay replays I5Gated1000 + Consensus600 items) —
check an experiment's `PREREGISTRATION.md`/provenance files for what it depends on before assuming
independence.

Not every harness directory has its code unpacked — `Experiment_Concensus600`'s harness exists
only inside its `.zip`; the others (`Syco30`, `Decomp30`, `Review160`, `Blind80`, `I5Gated1000`,
`PositionReplay`) have both the unpacked directory and the archival zip.

Top-level `LICENSE-CONTENT.md` explains the dual-license split: software (harness code, tests,
scripts) is BSD-3-Clause-Clear; research content (analyses, preregistrations, result artifacts) is
CC BY 4.0. Upstream datasets (SycoBench-600, MMLU) keep their own terms and are not vendored.

## Working inside one harness

Each `ccrc_<name>_harness_v<ver>/` is an independent Python package — there is no repo-wide build.
`cd` into the specific harness directory before doing anything:

```bash
cd Experiment_<Name>/ccrc_<name>_harness_v<ver>

python -m venv .venv
# Windows: .venv\Scripts\activate
python -m pip install -U pip
pip install -r requirements.txt      # runtime dep is just `requests`; dev adds `pytest`
cp config.example.json config.json   # then set model_id to the exact LM Studio model key
```

Run the offline test suite (no network/model required):

```bash
pytest -q
# or, dependency-free:
python tools/run_offline_tests.py
```

Tests live in `tests/` and typically cover `design.py` (counterbalancing/permutation logic),
`analysis.py` (statistics), and — critically — `test_frozen.py`, which re-verifies the SHA-256
hashes and provenance counts of the experiment's frozen inputs (`frozen/FROZEN_SHA256.txt`). If
you touch anything under `frozen/`, `test_frozen.py` is expected to fail unless the change is a
deliberate, freshly-preregistered new experiment version.

Running an actual experiment requires a local LM Studio server with the exact pinned model loaded
and the Responses API transport (candidate logprobs for A/B/C/D). The CLI pipeline is staged and
resumable; exact subcommand names vary slightly by harness version (`prepare`/`run-native` in
early harnesses vs. `init`/`run` in later ones — check `harness/cli.py`'s `add_parser` calls or
that experiment's own `README.md`), but the shape is always:

```bash
python -m harness.cli doctor --config config.json --out doctor.json
python -m harness.cli init --config config.json --doctor doctor.json --out <experiment_dir>
python -m harness.cli transport-check --config config.json --out <experiment_dir>
python -m harness.cli run --config config.json --out <experiment_dir> [--limit N]
python -m harness.cli validate --out <experiment_dir>
python -m harness.cli finalize --config config.json --out <experiment_dir>
```

`doctor` verifies the LM Studio runtime/model identity against `config.json`'s `expected_model`
block before anything else is allowed to run. `finalize` requires full validation to pass and
writes `analysis.json`, `cell_results.csv`, `validation.json`, `FINALIZED.json`, and a SHA-256
hash ledger (`hashes.sha256`).

## Architecture shared across harnesses

Every harness package follows the same module split under `harness/`:

- `design.py` — counterbalancing: builds the frozen call plan (item × permutation × replicate
  stream), assigns display-slot orderings (e.g. Williams-square latin-square balancing so no
  option letter is systematically favored), and maps canonical ↔ displayed answer letters.
- `model_identity.py` / `lmstudio.py` — talks to the local LM Studio server and hard-fails if the
  loaded model's architecture, quantization, param count, or capabilities don't exactly match
  `config.json`'s pinned `expected_model`. This is a deliberate gate: results are only trusted
  against a single verified runtime snapshot.
- `preflight.py` — the `doctor` check combining transport + model identity verification.
- `runner.py` — executes the (resumable, `run_key`-addressed) call plan against the model.
- `parsing.py` — extracts the single-letter answer from model output, with a bounded format-retry.
- `analysis.py` — turns raw run rows into the experiment's statistical decision (repairs/harms,
  gate pass/fail, significance tests).
- `validate.py` — independent re-validation of a completed run (hash/shape/logic checks), plus
  `verify_frozen()` for the frozen-input integrity check used by `test_frozen.py`.
- `util.py` — canonical JSON, SHA-256 hashing, and `stable_seed()` — a deterministic seed derived
  from `(base_seed, *parts)` so every model call's sampling seed is reproducible from the frozen
  call plan alone.

`tools/build_frozen.py` generates the `frozen/` directory (items, call plan, provenance) from
upstream data before a run starts; `tools/package_release.py` builds the archival `.zip` snapshot.

## Critical invariants when touching harness code or experiment data

- **Frozen means frozen.** Once a preregistration is written and `frozen/FROZEN_SHA256.txt` is
  generated, do not alter thresholds, prompts, seeds, model/runtime settings, or selection rules
  for that experiment — `assert_config_frozen()` / `verify_frozen()` exist specifically to catch
  this. If a change is genuinely needed, it defines a *new* experiment version: new directory, new
  preregistration written and frozen *before* looking at outcomes, original run left untouched.
- **The logprob margin is a routing signal, not a correctness judge.** Don't write analysis or
  code that treats a high-confidence answer as more likely correct — RESEARCH_STATE.md §3 and §9
  are explicit that this must never be conflated.
- **Blind means blind.** Verifier/re-derivation prompts must never leak the model's prior answer,
  prior reasoning, or any hint that a prior attempt existed — several experiments (Review160,
  Blind80) exist specifically to isolate this variable.
- **Report full outcome accounting, not accuracy alone.** Repairs, harms, abstentions, coverage,
  inference-call cost, and paired uncertainty intervals are the expected reporting shape (see any
  `*_Analysis_*.md` / `*_Audit_Certificate_*.md` for the pattern to follow).
