# CCRC Syco30 Harness v0.1.2

Deterministic, auditable data collection for the first local-model measurement stage.

**Target environment:** LM Studio + Qwen 2.5 7B Instruct GGUF Q4_K_M.

The harness runs a frozen 30-item SycoBench-600 subset and preserves exact API message histories, raw outputs, parse behavior, generated-token logprobs when LM Studio exposes them, lineage, runtime metadata, hashes, and analysis-ready JSONL/CSV.

## What changed in v0.1.1

This patch was made **before any experimental data was collected**.

1. `/v1/responses` is now explicitly the **primary experimental transport**.
2. `/v1/chat/completions` is retained only as a protocol/serialization sanity control.
3. New `transport-check` compares both endpoints on identical explicit message histories from two frozen items before the full run.
4. A full run is blocked unless the transport check passes.
5. Responses generated-token logprobs are required by default.
6. The check never uses `previous_response_id`; every request carries explicit stateless history.
7. `logit_bias` remains prohibited.
8. Default `max_tokens` is now **128**, matching the released SycoBench runner rather than the previous 16-token convenience limit.
9. Format-retry lineage now matches SycoBench: if the first response is unparsable and a format retry is required, the **retry response** becomes the benchmark response carried into follow-ups, while the first response remains preserved.
10. Question/variant families and follow-up execution order are deterministically shuffled to reduce fixed-order runtime confounding.
11. Run records now say explicitly that `prompt_sha256` hashes the **API message structure before LM Studio's chat-template serialization**.
12. Doctor records Python/platform/requests metadata and whether Responses actually returned logprobs.
13. Manifest records the harness version and aggregate package-tree hash.


## Authentication (v0.1.2)

If LM Studio's **Require Authentication** option is enabled, set the documented `LM_API_TOKEN` environment variable before running the harness.

PowerShell:

```powershell
$env:LM_API_TOKEN="paste-your-LM-Studio-token-here"
```

Run `doctor` again from that **same PowerShell window**. The harness sends the token only in the `Authorization: Bearer ...` request header. It records only whether a token was present; the token value is never written to experiment artifacts.

Clear it after the experiment with:

```powershell
Remove-Item Env:LM_API_TOKEN
```

If the server is intentionally bound strictly to localhost, you can instead disable **Require Authentication** in LM Studio's Developer → Server Settings. Keep authentication enabled if LM Studio is exposed to your LAN or another interface.


## Why Responses is primary

For this experiment, Responses is not assumed to make Qwen reason better. Its value is observability: current LM Studio Open Responses support can expose generated-token logprobs and top candidate tokens.

Chat Completions remains useful because SycoBench's public runner uses an OpenAI-compatible Chat Completions interface. We therefore keep it as a small diagnostic control, not as a second experimental transport.

**Never mix transports inside the frozen native run.**

## Important limitation

`prompt_sha256` covers the canonical API messages we send. LM Studio applies the model's chat template after receiving those messages. The harness does not claim that the hash is a hash of the final tokenized prompt.

For the two-item preflight, you can optionally run:

```bash
lms log stream --source model --filter input,output --json
```

in another terminal while `transport-check` runs. That lets you visually inspect LM Studio's final formatted model I/O without making that CLI stream part of the canonical dataset.

## Quantization rule

Q4_K_M is the system under test. Treat its absolute logprob values as belonging to that exact quantized model/runtime. Do not infer FP16-equivalent margins.

If a meaningful effect appears, later rerun a small frozen subset under Q8 or FP16 if practical.

## Setup

### 1. Start LM Studio

Load **Qwen 2.5 7B Instruct Q4_K_M** and start the local server, normally:

```text
http://localhost:1234
```

### 2. Environment

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item config.example.json config.json
```

macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
```

Leave `"model_id": null` until `doctor` tells you the exact loaded ID, unless only one LLM is loaded.

---

# Frozen execution sequence

## A. Doctor

```bash
python -m harness.cli doctor \
  --config config.json \
  --out experiment/doctor.json
```

Confirm:

- the intended model is loaded;
- Responses works;
- Responses returns generated-token logprobs;
- Chat Completions works;
- runtime/model metadata looks correct.

If multiple model IDs are visible, put the exact intended ID into `config.json` and rerun doctor.

## B. Prepare/freeze the 30 items

With a local SycoBench clone:

```bash
python -m harness.cli prepare \
  --questions C:\path\to\sycobench-600\data\questions.json \
  --config config.json \
  --out experiment
```

Or let the harness fetch the pinned v1.0.1 dataset:

```bash
python -m harness.cli prepare --config config.json --out experiment
```

Outputs:

```text
experiment/
  doctor.json
  items.jsonl
  manifest.json
  hashes.sha256
```

The 30-item selection is deterministic, approximately balanced by domain/difficulty, and excludes exact duplicate question stems.

**Do not regenerate this subset after seeing results.**

## C. Transport equivalence sanity check

Run the frozen two-item endpoint check:

```bash
python -m harness.cli transport-check \
  --config config.json \
  --experiment experiment \
  --n-items 2
```

For each of two frozen questions it sends the same explicit message history through:

- `/v1/responses`
- `/v1/chat/completions`

It tests two prompt shapes:

1. baseline MCQ;
2. multi-turn authority follow-up with a fixed registered assistant history.

The fixed history is deliberate: it prevents endpoint A's generated baseline from changing the input sent to endpoint B.

`transport_check.json` reports:

- endpoint errors;
- parsed-answer agreement;
- raw-text disagreement;
- Responses logprob availability;
- whether the requested seed was actually sent;
- exact API-message hashes.

**PASS is a preflight sanity condition, not proof of distributional identity.**

## D. Two-item native acceptance run

```bash
python -m harness.cli run-native \
  --config config.json \
  --experiment experiment \
  --limit 2 \
  --variants 1
```

Then:

```bash
python -m harness.cli validate --experiment experiment
```

Manually inspect those two question families.

## E. Full frozen native run

```bash
python -m harness.cli run-native \
  --config config.json \
  --experiment experiment \
  --variants 3
```

A full run refuses to start if `transport_check.json` is absent or not `PASS`.

The released SycoBench protocol is multi-turn:

1. baseline question;
2. fresh explicit-history follow-up for doubt;
3. fresh explicit-history follow-up for authority;
4. fresh explicit-history follow-up for wrong suggestion;
5. correct suggestion only when baseline was wrong.

Three paraphrase variants are used.

For 30 items, the minimum is:

```text
30 × 3 × (1 baseline + 3 misleading-pressure calls) = 360 generations
```

plus correct-suggestion calls for baseline-wrong cases.

## F. Validate before interpretation

```bash
python -m harness.cli validate --experiment experiment
```

Validation checks:

- duplicate run keys;
- missing question/variant/condition records;
- exact baseline lineage;
- prompt hashes;
- mixed transports;
- raw-response retention;
- correct-suggestion conditional presence;
- parse/retry integrity.

## G. Summarize

```bash
python -m harness.cli summarize --experiment experiment
```

Outputs:

```text
experiment/
  doctor.json
  transport_check.json
  manifest.json
  items.jsonl
  runs.jsonl
  summary.csv
  summary.json
  hashes.sha256
```

Send that directory back unchanged.

---

# Data semantics

## Format retries

The upstream SycoBench runner performs a format retry if the first output cannot be parsed.

v0.1.1 preserves both:

```text
first raw output  -> retained
retry raw output  -> retained
benchmark response -> retry output if retry occurred
```

The benchmark response—not the malformed first output—is what appears as the assistant turn in later pressure conditions. This now matches the released SycoBench protocol.

## Logprobs

Responses may provide:

- selected generated token logprob;
- top candidate token logprobs.

This is **not the complete raw vocabulary logit tensor**.

For a one-letter MCQ, candidate A/B/C/D logprobs are still useful. The harness preserves raw token strings and also extracts normalized A/B/C/D candidate logprobs where available.

## No hidden state

The harness does **not** use:

```text
previous_response_id
```

Every multi-turn request reconstructs the complete registered message history explicitly.

## No distribution forcing

The harness does not use:

- `logit_bias`;
- JSON grammar;
- schema-constrained output;
- tool calls;
- hidden agent state.

The one-letter instruction is ordinary prompt text, matching SycoBench.

---

# Stage boundary

v0.1.1 still intentionally does **not** implement:

- M5;
- authority-versus-verdict decomposition;
- context-ledger attribution;
- activation steering;
- attention/KV intervention.

Those are downstream of the native measurement.

The next architectural decision should be made from the collected data, not added before it.
