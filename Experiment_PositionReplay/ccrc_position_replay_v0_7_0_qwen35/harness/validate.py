from __future__ import annotations

from pathlib import Path
from typing import Any

from .design import LETTERS, validate_call_plan, verifier_messages
from .parsing import exact_one_letter, parse_mcq_letter
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


def validate_experiment(experiment_dir: Path, full: bool = False) -> dict[str, Any]:
    errors = verify_frozen(experiment_dir / "frozen")
    items = read_jsonl(experiment_dir / "frozen" / "replay_items.jsonl")
    plan = read_jsonl(experiment_dir / "frozen" / "call_plan.jsonl")
    errors.extend(validate_call_plan(items, plan))
    item_by_id = {x["question_id"]: x for x in items}
    plan_by_key = {x["run_key"]: x for x in plan}
    runs = read_jsonl(experiment_dir / "runs.jsonl")
    if len({x.get("run_key") for x in runs}) != len(runs):
        errors.append("Duplicate run_key in runs.jsonl")
    if full and len(runs) != len(plan):
        errors.append(f"Full validation expected {len(plan)} cells, observed {len(runs)}")

    manifest = read_json(experiment_dir / "manifest.json")
    cfg = manifest["config"]
    for row in runs:
        key = row.get("run_key")
        cell = plan_by_key.get(key)
        if cell is None:
            errors.append(f"Unplanned replay cell: {key}")
            continue
        item = item_by_id[cell["question_id"]]
        for field in (
            "question_id", "placement", "replicate_stream", "seed", "option_order",
            "display_to_canonical", "correct_display_slot", "call_index",
        ):
            if row.get(field) != cell.get(field):
                errors.append(f"{key}: frozen field mismatch: {field}")
        messages = verifier_messages(item, cell["option_order"])
        prompt_hash = sha256_text(canonical_json(messages))
        if row.get("messages") != messages or row.get("prompt_sha256") != prompt_hash:
            errors.append(f"{key}: prompt mismatch")
        if row.get("parsed_answer") not in LETTERS or row.get("parsed_display_answer") not in LETTERS:
            errors.append(f"{key}: unparsable final answer")
        else:
            mapped = cell["display_to_canonical"].get(row["parsed_display_answer"])
            if mapped != row["parsed_answer"]:
                errors.append(f"{key}: display/canonical mapping mismatch")
        if not row.get("exact_format"):
            errors.append(f"{key}: final output is not exact one-letter format")
        if row.get("correct") != (row.get("parsed_answer") == item["correct_answer"]):
            errors.append(f"{key}: correctness mismatch")
        if row.get("model_snapshot_sha256") != cfg.get("required_runtime_snapshot_sha256"):
            errors.append(f"{key}: model runtime snapshot mismatch")
        if row.get("model_id") != cfg.get("model_id"):
            errors.append(f"{key}: model id mismatch")
        if row.get("temperature") != float(cfg.get("temperature", 0.0)) or row.get("top_p") != float(cfg.get("top_p", 1.0)):
            errors.append(f"{key}: decoding settings mismatch")
        if row.get("prior_answer_visible") or row.get("stateful_continuation_used"):
            errors.append(f"{key}: answer leakage/stateful continuation")
        first = row.get("first_attempt") or {}
        retry = row.get("format_retry")
        first_raw = first.get("raw_output") or ""
        first_display = parse_mcq_letter(first_raw)
        first_canonical = cell["display_to_canonical"].get(first_display) if first_display else None
        if first.get("parsed_display_answer") != first_display or first.get("parsed_answer") != first_canonical:
            errors.append(f"{key}: first-attempt parse reconstruction mismatch")
        if bool(first.get("exact_format")) != exact_one_letter(first_raw):
            errors.append(f"{key}: first-attempt format reconstruction mismatch")
        if retry is not None:
            retry_raw = retry.get("raw_output") or ""
            retry_display = parse_mcq_letter(retry_raw)
            retry_canonical = cell["display_to_canonical"].get(retry_display) if retry_display else None
            if retry.get("parsed_display_answer") != retry_display or retry.get("parsed_answer") != retry_canonical:
                errors.append(f"{key}: retry parse reconstruction mismatch")
            if bool(retry.get("exact_format")) != exact_one_letter(retry_raw):
                errors.append(f"{key}: retry format reconstruction mismatch")
        if first.get("reasoning_detected") or (retry or {}).get("reasoning_detected"):
            errors.append(f"{key}: reasoning telemetry detected")
        if first.get("exact_format") and retry is not None:
            errors.append(f"{key}: retry occurred after an exact-format first output")
        if not first.get("exact_format") and bool(cfg.get("format_retry", True)) and retry is None:
            errors.append(f"{key}: frozen format retry was omitted")
        if row.get("model_call_count") != 1 + int(retry is not None):
            errors.append(f"{key}: model_call_count mismatch")

    report = {
        "schema_version": "ccrc.position_replay.validation.v0.7.0",
        "mode": "full" if full else "partial",
        "status": "PASS" if not errors else "FAIL",
        "planned_cells": len(plan),
        "completed_cells": len(runs),
        "actual_model_calls": sum(int(x.get("model_call_count", 1)) for x in runs),
        "errors": errors,
    }
    write_json(experiment_dir / "validation.json", report)
    return report
