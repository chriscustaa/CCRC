from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .design import FORMAT_RETRY, LETTERS, verifier_messages
from .lmstudio import LMStudioClient
from .model_identity import resolve_model_strict
from .parsing import answer_candidate_logprobs, exact_one_letter, parse_mcq_letter
from .util import append_jsonl, canonical_json, read_jsonl, sha256_text


def generate_with_transport_retry(client: LMStudioClient, retries: int, **kwargs: Any) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return client.generate(**kwargs)
        except Exception as exc:  # transport errors are logged by the caller on final failure
            last = exc
            if attempt >= retries:
                break
            time.sleep(0.5 * (2**attempt))
    raise RuntimeError(f"Transport failed after {retries + 1} attempts: {last}")


def _call(client: LMStudioClient, cfg: dict[str, Any], model_id: str, messages: list[dict[str, str]], seed: int) -> dict[str, Any]:
    result = generate_with_transport_retry(
        client=client,
        retries=int(cfg.get("transport_retries", 2)),
        transport=cfg.get("transport", "responses"),
        model=model_id,
        messages=messages,
        temperature=float(cfg.get("temperature", 0.0)),
        top_p=float(cfg.get("top_p", 1.0)),
        max_tokens=int(cfg.get("max_tokens", 128)),
        seed=seed,
        top_logprobs=int(cfg.get("top_logprobs", 20)),
        presence_penalty=float(cfg.get("presence_penalty", 0.0)),
        frequency_penalty=float(cfg.get("frequency_penalty", 0.0)),
    )
    if bool(cfg.get("require_reasoning_off", True)) and result.get("reasoning_detected"):
        raise RuntimeError("Reasoning-off invariant violated")
    return result


def _remap_scores(display_scores: dict[str, float | None], mapping: dict[str, str]) -> dict[str, float | None]:
    out = {letter: None for letter in LETTERS}
    for display, canonical in mapping.items():
        out[canonical] = display_scores.get(display)
    return out


def _result_payload(result: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    raw = result.get("text") or ""
    parsed_display = parse_mcq_letter(raw)
    parsed = mapping.get(parsed_display) if parsed_display else None
    display_scores = answer_candidate_logprobs(result.get("token_logprobs"))
    return {
        "raw_output": raw,
        "parsed_display_answer": parsed_display,
        "parsed_answer": parsed,
        "exact_format": exact_one_letter(raw),
        "candidate_logprobs_display": display_scores,
        "candidate_logprobs_canonical": _remap_scores(display_scores, mapping),
        "token_logprobs": result.get("token_logprobs"),
        "reasoning_tokens": result.get("reasoning_tokens"),
        "reasoning_content_present": result.get("reasoning_content_present"),
        "reasoning_detected": result.get("reasoning_detected"),
        "usage": result.get("usage"),
        "latency_s": result.get("latency_s"),
        "transport_request_meta": result.get("request_meta"),
        "transport_response_meta": result.get("meta"),
        "raw_response": result.get("raw_response"),
    }


def run_replay(
    cfg: dict[str, Any],
    items: list[dict[str, Any]],
    plan: list[dict[str, Any]],
    experiment_dir: Path,
    limit: int | None = None,
) -> dict[str, int]:
    client = LMStudioClient(cfg["lmstudio_base_url"], timeout_s=float(cfg.get("timeout_s", 120)))
    model_id, identity = resolve_model_strict(client, cfg)
    required_snapshot = cfg.get("required_runtime_snapshot_sha256")
    observed_snapshot = identity.get("model_snapshot_sha256")
    if required_snapshot and observed_snapshot != required_snapshot:
        raise RuntimeError(
            "Runtime snapshot mismatch: "
            f"required={required_snapshot}, observed={observed_snapshot}"
        )

    item_by_id = {x["question_id"]: x for x in items}
    run_path = experiment_dir / "runs.jsonl"
    existing_rows = read_jsonl(run_path)
    existing = {x["run_key"]: x for x in existing_rows}
    if len(existing) != len(existing_rows):
        raise RuntimeError("Duplicate run_key already present in runs.jsonl")

    completed_now = 0
    retry_calls = 0
    for cell in sorted(plan, key=lambda x: x["call_index"]):
        if cell["run_key"] in existing:
            continue
        if limit is not None and completed_now >= limit:
            break
        item = item_by_id[cell["question_id"]]
        messages = verifier_messages(item, cell["option_order"])
        prompt_hash = sha256_text(canonical_json(messages))
        if prompt_hash != cell["prompt_sha256"]:
            raise RuntimeError(f"Frozen prompt hash mismatch for {cell['run_key']}")

        first_result = _call(client, cfg, model_id, messages, int(cell["seed"]))
        first = _result_payload(first_result, cell["display_to_canonical"])
        retry = None
        final = first
        if not first["exact_format"] and bool(cfg.get("format_retry", True)):
            retry_calls += 1
            retry_messages = list(messages) + [{"role": "user", "content": FORMAT_RETRY}]
            retry_result = _call(client, cfg, model_id, retry_messages, int(cell["seed"]) + 1)
            retry = {
                "messages": retry_messages,
                "prompt_sha256": sha256_text(canonical_json(retry_messages)),
                **_result_payload(retry_result, cell["display_to_canonical"]),
            }
            final = retry

        rec = {
            "schema_version": "ccrc.position_replay.run.v0.7.0",
            "experiment_id": cfg["experiment_id"],
            **cell,
            "subject": item.get("subject"),
            "correct_answer": item["correct_answer"],
            "messages": messages,
            "prompt_sha256": prompt_hash,
            "prompt_hash_scope": "canonical_api_messages_pre_chat_template",
            "model_id": model_id,
            "model_snapshot_sha256": observed_snapshot,
            "transport": cfg.get("transport", "responses"),
            "temperature": float(cfg.get("temperature", 0.0)),
            "top_p": float(cfg.get("top_p", 1.0)),
            "presence_penalty": float(cfg.get("presence_penalty", 0.0)),
            "frequency_penalty": float(cfg.get("frequency_penalty", 0.0)),
            "prior_answer_visible": False,
            "stateful_continuation_used": False,
            "first_attempt": first,
            "format_retry": retry,
            "model_call_count": 1 + int(retry is not None),
            "parsed_display_answer": final["parsed_display_answer"],
            "parsed_answer": final["parsed_answer"],
            "exact_format": final["exact_format"],
            "correct": final["parsed_answer"] == item["correct_answer"] if final["parsed_answer"] else None,
        }
        if rec["parsed_answer"] not in LETTERS or not rec["exact_format"]:
            raise RuntimeError(f"Cell remained noncompliant after frozen retry rule: {cell['run_key']}")
        append_jsonl(run_path, rec)
        existing[rec["run_key"]] = rec
        completed_now += 1

    return {
        "completed_before": len(existing_rows),
        "completed_now": completed_now,
        "completed_total": len(existing),
        "planned_cells": len(plan),
        "retry_calls_now": retry_calls,
    }
