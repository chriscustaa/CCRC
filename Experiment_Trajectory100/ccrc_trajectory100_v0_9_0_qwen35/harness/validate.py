from __future__ import annotations

from pathlib import Path
from typing import Any

from .design import LETTERS, stage_messages, validate_call_plan
from .parsing import answer_candidate_logprobs, exact_one_letter, parse_mcq_letter
from .util import canonical_json, read_json, read_jsonl, sha256_file, sha256_text, write_json


def verify_frozen(frozen_dir: Path) -> list[str]:
    errors = []
    expected_files = {}
    for line in (frozen_dir / "FROZEN_SHA256.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            expected, name = line.split(maxsplit=1)
            expected_files[name.strip()] = expected
    for name, expected in expected_files.items():
        path = frozen_dir / name
        if not path.exists():
            errors.append(f"Missing frozen file: {name}")
        elif sha256_file(path) != expected:
            errors.append(f"Frozen hash mismatch: {name}")
    return errors


def _gap(scores: dict[str, float | None]) -> float | None:
    vals = sorted((float(v) for v in scores.values() if v is not None), reverse=True)
    return vals[0] - vals[1] if len(vals) >= 2 else None


def validate_experiment(experiment_dir: Path, full: bool = False) -> dict[str, Any]:
    errors = verify_frozen(experiment_dir / "frozen")
    items = read_jsonl(experiment_dir / "frozen" / "pilot_items.jsonl")
    plan = read_jsonl(experiment_dir / "frozen" / "call_plan.jsonl")
    errors.extend(validate_call_plan(items, plan))
    item_by_id = {x["question_id"]: x for x in items}
    plan_by_key = {x["run_key"]: x for x in plan}
    runs = read_jsonl(experiment_dir / "runs.jsonl")
    if len({x.get("run_key") for x in runs}) != len(runs):
        errors.append("Duplicate run_key in runs.jsonl")
    if full and len(runs) != len(plan):
        errors.append(f"Full validation expected {len(plan)} cells, observed {len(runs)}")

    cfg = read_json(experiment_dir / "manifest.json")["config"]
    for row in runs:
        key = row.get("run_key")
        cell = plan_by_key.get(key)
        if cell is None:
            errors.append(f"Unplanned cell: {key}")
            continue
        item = item_by_id[cell["question_id"]]
        for field in ("question_id", "source_bundle", "stage", "stage_index", "seed", "call_index"):
            if row.get(field) != cell.get(field):
                errors.append(f"{key}: frozen field mismatch: {field}")
        messages = stage_messages(item, cell["stage"])
        prompt_hash = sha256_text(canonical_json(messages))
        if row.get("messages") != messages or row.get("prompt_sha256") != prompt_hash:
            errors.append(f"{key}: prompt mismatch")
        if row.get("parsed_answer") not in LETTERS or not row.get("exact_format"):
            errors.append(f"{key}: invalid final answer/format")
        if row.get("correct") != (row.get("parsed_answer") == item["correct_answer"]):
            errors.append(f"{key}: correctness mismatch")
        if row.get("model_snapshot_sha256") != cfg.get("required_runtime_snapshot_sha256"):
            errors.append(f"{key}: model runtime snapshot mismatch")
        if row.get("model_id") != cfg.get("model_id"):
            errors.append(f"{key}: model id mismatch")
        if row.get("temperature") != 0.0 or row.get("top_p") != 1.0:
            errors.append(f"{key}: decoding settings mismatch")
        if row.get("prior_answer_visible") or row.get("stateful_continuation_used"):
            errors.append(f"{key}: answer leakage/stateful continuation")
        final_attempt = row.get("format_retry") or row.get("first_attempt") or {}
        raw = final_attempt.get("raw_output") or ""
        if parse_mcq_letter(raw) != row.get("parsed_answer") or exact_one_letter(raw) != bool(row.get("exact_format")):
            errors.append(f"{key}: parse/format reconstruction mismatch")
        scores = answer_candidate_logprobs(final_attempt.get("token_logprobs"))
        if _gap(scores) != row.get("confidence_gap"):
            errors.append(f"{key}: confidence-gap reconstruction mismatch")
        if row.get("confidence_gap") is None:
            errors.append(f"{key}: missing confidence gap")
        if (row.get("first_attempt") or {}).get("reasoning_detected") or (row.get("format_retry") or {}).get("reasoning_detected"):
            errors.append(f"{key}: reasoning telemetry detected")
        retry = row.get("format_retry")
        first = row.get("first_attempt") or {}
        if first.get("exact_format") and retry is not None:
            errors.append(f"{key}: retry after valid first attempt")
        if not first.get("exact_format") and bool(cfg.get("format_retry", True)) and retry is None:
            errors.append(f"{key}: frozen format retry omitted")
        if row.get("model_call_count") != 1 + int(retry is not None):
            errors.append(f"{key}: model_call_count mismatch")

    report = {
        "schema_version": "ccrc.trajectory100.validation.v0.9.0",
        "mode": "full" if full else "partial",
        "status": "PASS" if not errors else "FAIL",
        "planned_cells": len(plan),
        "completed_cells": len(runs),
        "actual_model_calls": sum(int(x.get("model_call_count", 1)) for x in runs),
        "errors": errors,
    }
    write_json(experiment_dir / "validation.json", report)
    return report
