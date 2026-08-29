from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .design import LETTERS, condition_messages
from .lmstudio import LMStudioClient
from .model_identity import resolve_model_strict
from .parsing import answer_candidate_logprobs, exact_one_letter, parse_mcq_letter
from .util import append_jsonl, canonical_json, read_jsonl, sha256_text


def _transport_call(client: LMStudioClient, retries: int, **kwargs: Any) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return client.generate(**kwargs)
        except Exception as exc:
            last = exc
            if attempt >= retries:
                break
            time.sleep(0.5 * (2**attempt))
    raise RuntimeError(f"Transport failed after {retries + 1} attempts: {last}")


def _full_vector(result: dict[str, Any]) -> dict[str, float]:
    scores = answer_candidate_logprobs(result.get("token_logprobs"))
    missing = [x for x in LETTERS if scores.get(x) is None]
    if missing:
        raise RuntimeError(f"First-token top-logprobs omit required letter(s): {missing}")
    return {x: float(scores[x]) for x in LETTERS}  # type: ignore[arg-type]


def _gap(scores: dict[str, float]) -> float:
    vals = sorted(scores.values(), reverse=True)
    return vals[0] - vals[1]


def run_study(cfg: dict[str, Any], items: list[dict[str, Any]], plan: list[dict[str, Any]],
              experiment_dir: Path, limit: int | None = None) -> dict[str, int]:
    client = LMStudioClient(cfg["lmstudio_base_url"], timeout_s=float(cfg.get("timeout_s", 120)))
    model_id, identity = resolve_model_strict(client, cfg)
    observed_snapshot = identity.get("model_snapshot_sha256")
    required_snapshot = cfg.get("required_runtime_snapshot_sha256")
    if required_snapshot and observed_snapshot != required_snapshot:
        raise RuntimeError(f"Runtime snapshot mismatch: required={required_snapshot}, observed={observed_snapshot}")

    by_id = {x["question_id"]: x for x in items}
    run_path = experiment_dir / "runs.jsonl"
    prior_rows = read_jsonl(run_path)
    existing = {x["run_key"]: x for x in prior_rows}
    if len(existing) != len(prior_rows):
        raise RuntimeError("Duplicate run_key already present in runs.jsonl")

    completed_now = 0
    for cell in sorted(plan, key=lambda x: x["call_index"]):
        if cell["run_key"] in existing:
            continue
        if limit is not None and completed_now >= limit:
            break
        item = by_id[cell["question_id"]]
        messages = condition_messages(item, cell["condition"])
        prompt_hash = sha256_text(canonical_json(messages))
        if prompt_hash != cell["prompt_sha256"]:
            raise RuntimeError(f"Frozen prompt hash mismatch for {cell['run_key']}")

        result = _transport_call(
            client=client,
            retries=int(cfg.get("transport_retries", 2)),
            transport="responses",
            model=model_id,
            messages=messages,
            temperature=0.0,
            top_p=1.0,
            max_tokens=int(cfg.get("max_tokens", 32)),
            seed=int(cell["seed"]),
            top_logprobs=int(cfg.get("top_logprobs", 20)),
            presence_penalty=0.0,
            frequency_penalty=0.0,
        )
        if bool(cfg.get("require_reasoning_off", True)) and result.get("reasoning_detected"):
            raise RuntimeError(f"Reasoning-off invariant violated: {cell['run_key']}")
        request_meta = result.get("request_meta") or {}
        if bool(cfg.get("require_seed_accepted", True)) and (
            not request_meta.get("seed_sent") or request_meta.get("seed_rejected")
        ):
            raise RuntimeError(f"Seed was not accepted: {cell['run_key']}")
        raw = result.get("text") or ""
        parsed = parse_mcq_letter(raw)
        if not exact_one_letter(raw) or parsed not in LETTERS:
            raise RuntimeError(
                f"Cell did not return exactly one answer letter; no format retry is permitted: {cell['run_key']}"
            )
        vector = _full_vector(result)
        rec = {
            "schema_version": "ccrc.full_logit_syco120.run.v1.0.0",
            "experiment_id": cfg["experiment_id"],
            **cell,
            "subject": item["subject"],
            "confidence_stratum": item["confidence_stratum"],
            "correct_answer": item["correct_answer"],
            "baseline_answer": item["baseline_answer"],
            "baseline_correct": item["baseline_correct"],
            "baseline_gap": item["baseline_gap"],
            "wrong_suggestion": item["wrong_suggestion"],
            "messages": messages,
            "prompt_sha256": prompt_hash,
            "prompt_hash_scope": "canonical_api_messages_pre_chat_template",
            "model_id": model_id,
            "model_snapshot_sha256": observed_snapshot,
            "transport": "responses",
            "temperature": 0.0,
            "top_p": 1.0,
            "presence_penalty": 0.0,
            "frequency_penalty": 0.0,
            "prior_answer_visible": True,
            "stateful_continuation_used": False,
            "raw_output": raw,
            "parsed_answer": parsed,
            "exact_format": True,
            "candidate_logprobs": vector,
            "confidence_gap": _gap(vector),
            "correct": parsed == item["correct_answer"],
            "target_compliance": parsed == cell["suggested_answer"] if cell["suggested_answer"] else None,
            "token_logprobs": result.get("token_logprobs"),
            "reasoning_tokens": result.get("reasoning_tokens"),
            "reasoning_content_present": result.get("reasoning_content_present"),
            "reasoning_detected": result.get("reasoning_detected"),
            "usage": result.get("usage"),
            "latency_s": result.get("latency_s"),
            "transport_request_meta": request_meta,
            "transport_response_meta": result.get("meta"),
            "raw_response": result.get("raw_response"),
            "model_call_count": 1,
        }
        append_jsonl(run_path, rec)
        existing[rec["run_key"]] = rec
        completed_now += 1

    return {
        "completed_before": len(prior_rows),
        "completed_now": completed_now,
        "completed_total": len(existing),
        "planned_cells": len(plan),
        "actual_model_calls_now": completed_now,
    }

