# CCRC Syco30 Harness v0.2.0 — Qwen3.5 Cross-Model Replication

This package is a **new experiment profile**, not an extension of the completed Qwen2.5 dataset.

It runs the same frozen 30 SycoBench items against **Qwen3.5-9B Q4_K_M**, with Thinking functionally verified OFF, and preserves the Qwen2.5 experiment unchanged.

## Why this is the right next move

The Qwen2.5 screen showed strong, measurable context susceptibility. Before building the custom context-decomposition or M5 machinery, the highest-value cheap test is whether that susceptibility survives a major model-generation change.

The comparison is therefore:

```text
Qwen2.5-7B-Instruct Q4_K_M  → completed baseline
Qwen3.5-9B Q4_K_M           → this package
```

The experimental question is **not** which model is generally better. It is whether the pressure-sensitivity structure generalizes.

## Frozen replication controls

This profile requires:

```text
temperature       0.0
top_p             1.0
presence_penalty  0.0
frequency_penalty 0.0
Thinking          OFF
Responses API     primary
logprobs          required
```

LM Studio's Qwen3.5-9B model profile currently bakes in defaults including temperature 1, top-k 20, top-p 0.95, presence penalty 1.5, and Thinking ON. This harness explicitly overrides temperature, top-p, presence penalty and frequency penalty through the API. Top-k is not forced through `/v1/responses`; at temperature 0 the selected next token is greedy, so top-k does not change the argmax as long as the argmax remains admitted. The model profile has repeat penalty and min-p disabled.

The harness also **hard-fails if reasoning tokens/content appear** at any point.

## Exact item reuse

The completed Qwen2.5 experiment's frozen `items.jsonl` SHA-256 is:

```text
7924a926d70d82e4445633f2da1ecd92d4db44ba2cae6f2f185b795593f23ecb
```

v0.2.0 requires that exact file via `--source-items`; it will not silently reselect another 30 questions.

This turns the second run into an item-for-item replication rather than merely another sample produced from the same seed.

## Model identity

Expected profile:

```text
architecture: qwen35
params:       9B
quantization: Q4_K_M
format:       GGUF
display:      Qwen3.5 ... 9B
vision:       true
reasoning:    must expose an OFF-capable control
```

The exact LM Studio model key is discovered by `doctor` and then frozen.

## Important Thinking caveat

Qwen3.5 has had runtime-specific issues around disabling thinking in some LM Studio versions. For that reason this harness does **not** trust the GUI switch alone.

`doctor` runs three reasoning-prone probes through `/v1/responses` and requires:

```text
reasoning_tokens == 0
reasoning_content_present == false
```

The same invariant is checked after **every experimental generation**. If Thinking appears, the run stops immediately.

## Setup

Use a fresh directory/environment for this experiment. Keep the completed Qwen2.5 experiment untouched.

PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.example.json config.json
```

If LM Studio authentication is enabled:

```powershell
$env:LM_API_TOKEN="YOUR_TOKEN"
```

Do not put the token in `config.json`.

## Exact sequence

### 1. Load Qwen3.5-9B Q4_K_M

In LM Studio:

- unload Qwen2.5;
- load Qwen3.5-9B Q4_K_M;
- turn **Thinking OFF**;
- leave the model loaded for the entire run.

### 2. Discovery doctor

Keep:

```json
"model_id": null
```

Then:

```powershell
python -m harness.cli doctor --config config.json --out experiment_qwen35/doctor.json
```

A BLOCK caused only by null `model_id` is expected. Copy the exact `matching_loaded_candidates[].key` into `config.json`.

### 3. Final doctor

Rerun:

```powershell
python -m harness.cli doctor --config config.json --out experiment_qwen35/doctor.json
```

Do not continue unless the final output says:

```text
model_identity.status = PASS
full_run_preflight.ready_for_primary_transport = true
full_run_preflight.reasoning_off_probe_ok = true
status = PASS
```

### 4. Prepare by reusing the exact Qwen2.5 items

Point to the completed Qwen2.5 experiment's `items.jsonl`.

Example:

```powershell
python -m harness.cli prepare `
  --config config.json `
  --out experiment_qwen35 `
  --source-items "C:\Users\chris\Downloads\ccrc_syco30_harness_v0_1_3\experiment\items.jsonl"
```

The command hard-fails unless the file SHA-256 equals:

```text
7924a926d70d82e4445633f2da1ecd92d4db44ba2cae6f2f185b795593f23ecb
```

### 5. Transport check

```powershell
python -m harness.cli transport-check `
  --config config.json `
  --experiment experiment_qwen35 `
  --n-items 2
```

Must PASS with zero reasoning detected.

### 6. Two-item acceptance run

```powershell
python -m harness.cli run-native `
  --config config.json `
  --experiment experiment_qwen35 `
  --limit 2 `
  --variants 1
```

Then:

```powershell
python -m harness.cli validate --experiment experiment_qwen35
```

### 7. Full replication

Only after the acceptance checkpoint is clean:

```powershell
python -m harness.cli run-native `
  --config config.json `
  --experiment experiment_qwen35 `
  --variants 3
```

Then:

```powershell
python -m harness.cli validate --experiment experiment_qwen35
python -m harness.cli summarize --experiment experiment_qwen35
```

Zip `experiment_qwen35/` unchanged.

## Interpretation boundary

Do not append custom CCRC conditions to this run.

This experiment answers only:

> Does the native SycoBench susceptibility observed in Qwen2.5 persist in Qwen3.5 under the same frozen item set and a non-thinking greedy decision policy?

The context-decomposition experiment remains a separate next stage if this replication justifies it.
