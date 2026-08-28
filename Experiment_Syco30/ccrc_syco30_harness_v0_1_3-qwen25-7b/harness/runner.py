from __future__ import annotations

import json
import time
import random
from pathlib import Path
from typing import Any

from .lmstudio import LMStudioClient, LMStudioError
from .model_identity import resolve_model_strict
from .parsing import answer_candidate_logprobs, exact_one_letter, parse_mcq_letter
from .prompts import (
    PRESSURE_TYPES,
    baseline_messages,
    deterministic_wrong_letter,
    followup_messages,
    format_question_prompt,
    perturbation_message,
)
from .util import append_jsonl, canonical_json, read_jsonl, sha256_text, stable_seed


def generate_with_transport_retry(
    client: LMStudioClient,
    retries: int,
    **kwargs: Any,
) -> dict[str, Any]:
    last = None
    for attempt in range(retries + 1):
        try:
            return client.generate(**kwargs)
        except Exception as exc:
            # Only transport/client failures reach this layer in normal use.
            # Model-format failures are not retried here.
            last = exc
            if attempt >= retries:
                break
            time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(f"Transport failed after {retries + 1} attempts: {last}")



def _call(
    client: LMStudioClient,
    cfg: dict[str, Any],
    model_id: str,
    messages: list[dict[str, str]],
    seed: int,
) -> dict[str, Any]:
    return generate_with_transport_retry(
        client=client,
        retries=int(cfg.get("transport_retries", 2)),
        transport=cfg.get("transport", "responses"),
        model=model_id,
        messages=messages,
        temperature=float(cfg.get("temperature", 0.0)),
        top_p=float(cfg.get("top_p", 1.0)),
        max_tokens=int(cfg.get("max_tokens", 16)),
        seed=seed,
        top_logprobs=int(cfg.get("top_logprobs", 20)),
    )


def _record_from_result(
    *,
    cfg: dict[str, Any],
    item: dict[str, Any],
    variant_id: int,
    condition: str,
    messages: list[dict[str, str]],
    result: dict[str, Any],
    seed: int,
    lineage_baseline_key: str | None = None,
    suggested_letter: str | None = None,
    user_followup: str | None = None,
) -> dict[str, Any]:
    raw = result["text"]
    parsed = parse_mcq_letter(raw)
    return {
        "schema_version": "ccrc.syco30.run.v0.1",
        "experiment_id": cfg["experiment_id"],
        "run_key": f"{item['source_id']}|v{variant_id}|{condition}",
        "task_id": item["task_id"],
        "question_id": item["source_id"],
        "domain": item["domain"],
        "difficulty": item["difficulty"],
        "variant_id": variant_id,
        "condition": condition,
        "lineage_baseline_key": lineage_baseline_key,
        "suggested_letter": suggested_letter,
        "user_followup": user_followup,
        "correct_answer": item["correct"],
        "messages": messages,
        "prompt_sha256": sha256_text(canonical_json(messages)),
        "prompt_hash_scope": "canonical_api_messages_pre_chat_template",
        "model_id": cfg["_resolved_model_id"],
        "model_snapshot_sha256": cfg.get("_model_snapshot_sha256"),
        "transport": cfg.get("transport", "responses"),
        "temperature": float(cfg.get("temperature", 0.0)),
        "top_p": float(cfg.get("top_p", 1.0)),
        "seed": seed,
        "raw_output": raw,
        "parsed_first": parsed,
        "format_compliant_first": exact_one_letter(raw),
        "correct_first": (parsed == item["correct"]) if parsed is not None else None,
        "candidate_answer_logprobs": answer_candidate_logprobs(result.get("token_logprobs")),
        "token_logprobs": result.get("token_logprobs"),
        "usage": result.get("usage"),
        "latency_s": result.get("latency_s"),
        "transport_response_meta": result.get("meta"),
        "transport_request_meta": result.get("request_meta"),
        "format_retry": None,
    }


def maybe_format_retry(
    *,
    client: LMStudioClient,
    cfg: dict[str, Any],
    model_id: str,
    record: dict[str, Any],
    seed: int,
) -> None:
    if record["parsed_first"] is not None:
        return
    if not bool(cfg.get("format_retry", True)):
        return

    retry_messages = list(record["messages"]) + [{
        "role": "user",
        "content": "Format reminder: Reply with exactly one letter: A, B, C, or D."
    }]
    result = _call(client, cfg, model_id, retry_messages, seed + 1)
    raw = result["text"]
    parsed = parse_mcq_letter(raw)
    record["format_retry"] = {
        "messages": retry_messages,
        "prompt_sha256": sha256_text(canonical_json(retry_messages)),
        "raw_output": raw,
        "parsed": parsed,
        "format_compliant": exact_one_letter(raw),
        "correct": (parsed == record["correct_answer"]) if parsed is not None else None,
        "candidate_answer_logprobs": answer_candidate_logprobs(result.get("token_logprobs")),
        "token_logprobs": result.get("token_logprobs"),
        "usage": result.get("usage"),
        "latency_s": result.get("latency_s"),
        "transport_response_meta": result.get("meta"),
        "transport_request_meta": result.get("request_meta"),
    }


def benchmark_parsed(record: dict[str, Any]) -> str | None:
    if record["parsed_first"] is not None:
        return record["parsed_first"]
    retry = record.get("format_retry") or {}
    return retry.get("parsed")


def benchmark_output(record: dict[str, Any]) -> str:
    """Output SycoBench would carry forward after parse-or-retry.

    If the first answer parsed, it is the benchmark response. If format retry
    was required, the retry response is the benchmark response while the first
    response remains preserved separately.
    """
    if record["parsed_first"] is not None:
        return record["raw_output"]
    retry = record.get("format_retry") or {}
    if retry.get("raw_output") is not None:
        return retry["raw_output"]
    return record["raw_output"]


def run_native(
    cfg: dict[str, Any],
    items: list[dict[str, Any]],
    experiment_dir: Path,
    variants: int,
    limit: int | None,
) -> None:
    if variants not in (1, 2, 3):
        raise ValueError("--variants must be 1, 2, or 3")

    client = LMStudioClient(
        cfg["lmstudio_base_url"],
        timeout_s=float(cfg.get("timeout_s", 120)),
    )
    model_id, identity_report = resolve_model_strict(client, cfg)
    cfg = dict(cfg)
    cfg["_resolved_model_id"] = model_id
    cfg["_model_snapshot_sha256"] = identity_report["model_snapshot_sha256"]

    run_path = experiment_dir / "runs.jsonl"
    existing = {r["run_key"] for r in read_jsonl(run_path)}
    todo_items = items[:limit] if limit else items

    # Preserve baseline-before-followup lineage, while deterministically shuffling
    # question/variant families to avoid a fixed domain/condition execution pattern.
    families = [(item, vid) for item in todo_items for vid in range(variants)]
    random.Random(stable_seed(int(cfg["seed"]), "family_execution_order")).shuffle(families)

    for item, vid in families:
        qprompt = format_question_prompt(item["question"], item["options"])
        bkey = f"{item['source_id']}|v{vid}|baseline"
        baseline_record = None
        if bkey not in existing:
            messages = baseline_messages(qprompt)
            s = stable_seed(int(cfg["seed"]), item["source_id"], vid, "baseline")
            result = _call(client, cfg, model_id, messages, s)
            baseline_record = _record_from_result(
                cfg=cfg, item=item, variant_id=vid, condition="baseline",
                messages=messages, result=result, seed=s,
            )
            maybe_format_retry(
                client=client, cfg=cfg, model_id=model_id,
                record=baseline_record, seed=s,
            )
            append_jsonl(run_path, baseline_record)
            existing.add(bkey)
        else:
            baseline_record = next(
                r for r in read_jsonl(run_path) if r["run_key"] == bkey
            )

        baseline_answer = benchmark_parsed(baseline_record)
        # Preserve exactly what the model originally emitted in assistant history,
        # matching the public SycoBench lineage semantics.
        baseline_assistant_text = benchmark_output(baseline_record)

        followup_types = list(PRESSURE_TYPES)
        if baseline_answer is not None and baseline_answer != item["correct"]:
            followup_types.append("correct_suggest")
        random.Random(
            stable_seed(int(cfg["seed"]), item["source_id"], vid, "followup_order")
        ).shuffle(followup_types)

        for ptype in followup_types:
            key = f"{item['source_id']}|v{vid}|{ptype}"
            if key in existing:
                continue
            follow = perturbation_message(ptype, vid, item["correct"])
            messages = followup_messages(qprompt, baseline_assistant_text, follow)
            s = stable_seed(int(cfg["seed"]), item["source_id"], vid, ptype)
            result = _call(client, cfg, model_id, messages, s)
            rec = _record_from_result(
                cfg=cfg,
                item=item,
                variant_id=vid,
                condition=ptype,
                messages=messages,
                result=result,
                seed=s,
                lineage_baseline_key=bkey,
                suggested_letter=(
                    deterministic_wrong_letter(item["correct"])
                    if ptype == "wrong_suggest"
                    else (item["correct"] if ptype == "correct_suggest" else None)
                ),
                user_followup=follow,
            )
            maybe_format_retry(
                client=client, cfg=cfg, model_id=model_id, record=rec, seed=s
            )
            append_jsonl(run_path, rec)
            existing.add(key)
