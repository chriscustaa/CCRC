from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

from .lmstudio import LMStudioClient
from .model_identity import resolve_model_strict
from .parsing import answer_candidate_logprobs, exact_one_letter, parse_mcq_letter
from .prompts import CONDITIONS, baseline_messages, blind_messages, format_question_prompt, visible_self_messages
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
            last = exc
            if attempt >= retries:
                break
            time.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(f"Transport failed after {retries + 1} attempts: {last}")


def _call(client, cfg, model_id, messages, seed):
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
    if bool(cfg.get("require_reasoning_off", False)) and result.get("reasoning_detected"):
        raise RuntimeError("Reasoning-off invariant violated.")
    return result


def _benchmark_parsed(record: dict[str, Any]) -> str | None:
    if record.get("parsed_first") is not None:
        return record["parsed_first"]
    return (record.get("format_retry") or {}).get("parsed")


def _record(
    *,
    cfg,
    item,
    condition,
    messages,
    result,
    seed,
    frozen_baseline_answer,
    prior_answer_visible,
):
    raw = result["text"]
    parsed = parse_mcq_letter(raw)
    return {
        "schema_version": "ccrc.blind80.run.v0.5.0",
        "experiment_id": cfg["experiment_id"],
        "run_key": f"{item['source_id']}|{condition}",
        "task_id": item["task_id"],
        "question_id": item["source_id"],
        "domain": item["domain"],
        "difficulty": item["difficulty"],
        "condition": condition,
        "correct_answer": item["correct"],
        "frozen_baseline_answer": frozen_baseline_answer,
        "prior_answer_visible": prior_answer_visible,
        "messages": messages,
        "prompt_sha256": sha256_text(canonical_json(messages)),
        "prompt_hash_scope": "canonical_api_messages_pre_chat_template",
        "model_id": cfg["_resolved_model_id"],
        "model_snapshot_sha256": cfg.get("_model_snapshot_sha256"),
        "transport": cfg.get("transport", "responses"),
        "temperature": float(cfg.get("temperature", 0.0)),
        "top_p": float(cfg.get("top_p", 1.0)),
        "presence_penalty": float(cfg.get("presence_penalty", 0.0)),
        "frequency_penalty": float(cfg.get("frequency_penalty", 0.0)),
        "require_reasoning_off": bool(cfg.get("require_reasoning_off", False)),
        "reasoning_tokens": result.get("reasoning_tokens"),
        "reasoning_content_present": result.get("reasoning_content_present"),
        "reasoning_detected": result.get("reasoning_detected"),
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


def _maybe_format_retry(*, client, cfg, model_id, record, seed):
    if record["parsed_first"] is not None or not bool(cfg.get("format_retry", True)):
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
        "reasoning_detected": result.get("reasoning_detected"),
        "transport_response_meta": result.get("meta"),
        "transport_request_meta": result.get("request_meta"),
    }


def benchmark_parsed(record: dict[str, Any]) -> str | None:
    return _benchmark_parsed(record)


def run_blind80(cfg, items, experiment_dir: Path, limit: int | None):
    client = LMStudioClient(
        cfg["lmstudio_base_url"], timeout_s=float(cfg.get("timeout_s", 120))
    )
    model_id, identity = resolve_model_strict(client, cfg)
    cfg = dict(cfg)
    cfg["_resolved_model_id"] = model_id
    cfg["_model_snapshot_sha256"] = identity["model_snapshot_sha256"]

    run_path = experiment_dir / "runs.jsonl"
    existing_rows = read_jsonl(run_path)
    existing = {r["run_key"]: r for r in existing_rows}
    todo = items[:limit] if limit else items

    item_order = list(todo)
    random.Random(stable_seed(int(cfg["seed"]), "blind80_item_order")).shuffle(item_order)

    for item in item_order:
        qid = item["source_id"]
        qprompt = format_question_prompt(item["question"], item["options"])
        block_seed = stable_seed(int(cfg["seed"]), qid, "blind80_block")

        # B: one actual initial answer, generated once and frozen for S0 only.
        bkey = f"{qid}|B"
        b = existing.get(bkey)
        if b is None:
            messages = baseline_messages(qprompt)
            result = _call(client, cfg, model_id, messages, block_seed)
            b = _record(
                cfg=cfg, item=item, condition="B", messages=messages,
                result=result, seed=block_seed, frozen_baseline_answer=None,
                prior_answer_visible=False,
            )
            _maybe_format_retry(
                client=client, cfg=cfg, model_id=model_id, record=b, seed=block_seed
            )
            append_jsonl(run_path, b)
            existing[bkey] = b

        frozen = _benchmark_parsed(b)
        if frozen not in {"A", "B", "C", "D"}:
            raise RuntimeError(f"Baseline for {qid} remained unparsable after retry.")

        order = list(CONDITIONS)
        random.Random(stable_seed(int(cfg["seed"]), qid, "blind80_condition_order")).shuffle(order)

        for condition in order:
            key = f"{qid}|{condition}"
            if key in existing:
                # Resume integrity.
                if existing[key].get("frozen_baseline_answer") != frozen:
                    raise RuntimeError(f"Frozen B prefix drift on resumed row: {key}")
                continue

            if condition == "S0":
                messages = visible_self_messages(qprompt, frozen)
                prior_visible = True
            else:
                messages = blind_messages(qprompt, condition)
                prior_visible = False

            result = _call(client, cfg, model_id, messages, block_seed)
            rec = _record(
                cfg=cfg, item=item, condition=condition, messages=messages,
                result=result, seed=block_seed, frozen_baseline_answer=frozen,
                prior_answer_visible=prior_visible,
            )
            _maybe_format_retry(
                client=client, cfg=cfg, model_id=model_id, record=rec, seed=block_seed
            )
            append_jsonl(run_path, rec)
            existing[key] = rec
