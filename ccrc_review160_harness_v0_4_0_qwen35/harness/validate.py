from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .prompts import CONDITIONS, baseline_messages, followup_messages, format_question_prompt
from .runner import benchmark_parsed
from .util import canonical_json, read_json, read_jsonl, sha256_text


def validate_experiment(
    experiment_dir: Path,
    require_full: bool = False,
) -> dict[str, Any]:
    items = read_jsonl(experiment_dir / "items.jsonl")
    excluded = read_jsonl(experiment_dir / "excluded_items.jsonl")
    targets = read_jsonl(experiment_dir / "targets.jsonl")
    runs = read_jsonl(experiment_dir / "runs.jsonl")
    manifest = read_json(experiment_dir / "manifest.json")
    errors, warnings = [], []

    item_by = {x["source_id"]: x for x in items}
    excluded_ids = {x["source_id"] for x in excluded}
    target_by = {x["question_id"]: x["pressure_target"] for x in targets}

    if len(item_by) != len(items):
        errors.append("Duplicate source_id in items.jsonl")
    overlap = set(item_by) & excluded_ids
    if overlap:
        errors.append(f"Held-out leakage: {len(overlap)} selected IDs appear in excluded set")
    if set(target_by) != set(item_by):
        errors.append("targets.jsonl does not exactly match selected items")
    for qid, target in target_by.items():
        if target == item_by[qid]["correct"]:
            errors.append(f"Pressure target equals ground truth: {qid}")

    keys = [r.get("run_key") for r in runs]
    if len(keys) != len(set(keys)):
        errors.append("Duplicate run_key")
    run_by = {r["run_key"]: r for r in runs}

    frozen_model = (manifest.get("planned_model") or {}).get("model_id")
    frozen_snapshot = (manifest.get("planned_model") or {}).get("observed_snapshot_sha256")

    for r in runs:
        qid = r["question_id"]
        if qid not in item_by:
            errors.append(f"Unknown question_id: {qid}")
            continue
        item = item_by[qid]
        target = target_by[qid]

        if r.get("pressure_target") != target:
            errors.append(f"Pressure-target drift: {r['run_key']}")
        if r.get("model_id") != frozen_model:
            errors.append(f"Model ID drift: {r['run_key']}")
        if r.get("model_snapshot_sha256") != frozen_snapshot:
            errors.append(f"Runtime snapshot drift: {r['run_key']}")
        if r.get("reasoning_detected"):
            errors.append(f"Reasoning detected: {r['run_key']}")
        if float(r.get("temperature", -1)) != 0.0:
            errors.append(f"Temperature drift: {r['run_key']}")
        if float(r.get("top_p", -1)) != 1.0:
            errors.append(f"top_p drift: {r['run_key']}")
        if float(r.get("presence_penalty", -999)) != 0.0:
            errors.append(f"presence penalty drift: {r['run_key']}")
        if float(r.get("frequency_penalty", -999)) != 0.0:
            errors.append(f"frequency penalty drift: {r['run_key']}")

        qprompt = format_question_prompt(item["question"], item["options"])
        condition = r["condition"]
        if condition == "B":
            expected = baseline_messages(qprompt)
            if r.get("frozen_baseline_answer") is not None:
                errors.append(f"Baseline unexpectedly has frozen prefix: {r['run_key']}")
        else:
            b = run_by.get(f"{qid}|B")
            if b is None:
                errors.append(f"Follow-up lacks baseline row: {r['run_key']}")
                continue
            frozen = benchmark_parsed(b)
            if frozen not in {"A", "B", "C", "D"}:
                errors.append(f"Baseline prefix unparsable: {qid}")
                continue
            if r.get("frozen_baseline_answer") != frozen:
                errors.append(f"Frozen baseline prefix drift: {r['run_key']}")
            expected = followup_messages(qprompt, frozen, condition, target)
            assistants = [m["content"] for m in r["messages"] if m["role"] == "assistant"]
            if assistants != [frozen]:
                errors.append(f"Assistant prefix mismatch: {r['run_key']}")

        if r.get("messages") != expected:
            errors.append(f"Prompt construction mismatch: {r['run_key']}")
        if r.get("prompt_sha256") != sha256_text(canonical_json(expected)):
            errors.append(f"Prompt hash mismatch: {r['run_key']}")

        cand = r.get("candidate_answer_logprobs") or {}
        if item["correct"] not in cand:
            warnings.append(f"Missing correct-answer candidate logprob: {r['run_key']}")
        if condition in {"F", "P", "V"} and target not in cand:
            warnings.append(f"Missing target candidate logprob for M5 row: {r['run_key']}")

    # Every observed question must form a complete block.
    observed_qids = {r["question_id"] for r in runs}
    for qid in observed_qids:
        for condition in ["B"] + CONDITIONS:
            key = f"{qid}|{condition}"
            if key not in run_by:
                errors.append(f"Missing block member: {key}")

    if require_full:
        expected_count = len(items) * (1 + len(CONDITIONS))
        if len(items) != 160:
            errors.append(f"Full experiment requires 160 items, observed {len(items)}")
        if len(runs) != expected_count:
            errors.append(
                f"Full-run count mismatch: expected {expected_count}, observed {len(runs)}"
            )
        for qid in item_by:
            for condition in ["B"] + CONDITIONS:
                if f"{qid}|{condition}" not in run_by:
                    errors.append(f"Full run missing: {qid}|{condition}")

    return {
        "ok": not errors,
        "n_items": len(items),
        "n_excluded_items": len(excluded),
        "n_targets": len(targets),
        "n_runs": len(runs),
        "require_full": require_full,
        "errors": errors,
        "warnings": warnings,
    }
