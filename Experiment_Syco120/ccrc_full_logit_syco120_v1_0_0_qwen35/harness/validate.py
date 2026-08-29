from __future__ import annotations

from pathlib import Path
from typing import Any

from .design import LETTERS, condition_messages, validate_call_plan
from .parsing import answer_candidate_logprobs, exact_one_letter, parse_mcq_letter
from .util import canonical_json, read_json, read_jsonl, sha256_file, sha256_text, write_json


def verify_frozen(frozen_dir: Path) -> list[str]:
    errors: list[str] = []
    manifest = frozen_dir / "FROZEN_SHA256.txt"
    if not manifest.exists():
        return ["Missing FROZEN_SHA256.txt"]
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, name = line.split(maxsplit=1)
        path = frozen_dir / name.strip()
        if not path.exists():
            errors.append(f"Missing frozen file: {name.strip()}")
        elif sha256_file(path) != expected:
            errors.append(f"Frozen hash mismatch: {name.strip()}")
    return errors


def _full_vector(tokens: list[dict[str, Any]] | None) -> dict[str, float] | None:
    scores = answer_candidate_logprobs(tokens)
    if any(scores[x] is None for x in LETTERS):
        return None
    return {x: float(scores[x]) for x in LETTERS}  # type: ignore[arg-type]


def _gap(scores: dict[str, float]) -> float:
    vals = sorted(scores.values(), reverse=True)
    return vals[0] - vals[1]


def validate_experiment(experiment_dir: Path, full: bool = False) -> dict[str, Any]:
    errors = verify_frozen(experiment_dir / "frozen")
    items = read_jsonl(experiment_dir / "frozen" / "items.jsonl")
    plan = read_jsonl(experiment_dir / "frozen" / "call_plan.jsonl")
    errors.extend(validate_call_plan(items, plan))
    by_id = {x["question_id"]: x for x in items}
    by_key = {x["run_key"]: x for x in plan}
    runs = read_jsonl(experiment_dir / "runs.jsonl")
    if len({x.get("run_key") for x in runs}) != len(runs):
        errors.append("Duplicate run_key in runs.jsonl")
    if full and len(runs) != len(plan):
        errors.append(f"Full validation expected {len(plan)} cells, observed {len(runs)}")
    cfg = read_json(experiment_dir / "manifest.json")["config"]
    for row in runs:
        key = row.get("run_key")
        cell = by_key.get(key)
        if cell is None:
            errors.append(f"Unplanned cell: {key}")
            continue
        item = by_id[cell["question_id"]]
        for field in ("question_id", "condition", "suggested_answer", "seed", "call_index", "acceptance_cell"):
            if row.get(field) != cell.get(field):
                errors.append(f"{key}: frozen field mismatch: {field}")
        messages = condition_messages(item, cell["condition"])
        prompt_hash = sha256_text(canonical_json(messages))
        if row.get("messages") != messages or row.get("prompt_sha256") != prompt_hash:
            errors.append(f"{key}: prompt mismatch")
        raw = row.get("raw_output") or ""
        if not exact_one_letter(raw) or parse_mcq_letter(raw) != row.get("parsed_answer"):
            errors.append(f"{key}: output parse/format mismatch")
        if row.get("parsed_answer") not in LETTERS:
            errors.append(f"{key}: invalid parsed answer")
        vector = _full_vector(row.get("token_logprobs"))
        if vector is None:
            errors.append(f"{key}: missing complete A/B/C/D first-token logit vector")
        else:
            if vector != row.get("candidate_logprobs"):
                errors.append(f"{key}: stored candidate vector does not reconstruct")
            if _gap(vector) != row.get("confidence_gap"):
                errors.append(f"{key}: confidence gap does not reconstruct")
        if row.get("correct") != (row.get("parsed_answer") == item["correct_answer"]):
            errors.append(f"{key}: correctness mismatch")
        expected_compliance = row.get("parsed_answer") == cell["suggested_answer"] if cell["suggested_answer"] else None
        if row.get("target_compliance") != expected_compliance:
            errors.append(f"{key}: target compliance mismatch")
        if row.get("model_id") != cfg.get("model_id"):
            errors.append(f"{key}: model id mismatch")
        if row.get("model_snapshot_sha256") != cfg.get("required_runtime_snapshot_sha256"):
            errors.append(f"{key}: runtime snapshot mismatch")
        if row.get("temperature") != 0.0 or row.get("top_p") != 1.0:
            errors.append(f"{key}: decoding settings mismatch")
        if not row.get("prior_answer_visible") or row.get("stateful_continuation_used"):
            errors.append(f"{key}: transcript/statefulness mismatch")
        if row.get("reasoning_detected"):
            errors.append(f"{key}: reasoning telemetry detected")
        request = row.get("transport_request_meta") or {}
        if bool(cfg.get("require_seed_accepted", True)) and (not request.get("seed_sent") or request.get("seed_rejected")):
            errors.append(f"{key}: seed not accepted")
        if row.get("model_call_count") != 1:
            errors.append(f"{key}: model_call_count must equal 1")
    report = {
        "schema_version": "ccrc.full_logit_syco120.validation.v1.0.0",
        "mode": "full" if full else "partial",
        "status": "PASS" if not errors else "FAIL",
        "planned_cells": len(plan),
        "completed_cells": len(runs),
        "actual_model_calls": sum(int(x.get("model_call_count", 1)) for x in runs),
        "errors": errors,
    }
    write_json(experiment_dir / "validation.json", report)
    return report

