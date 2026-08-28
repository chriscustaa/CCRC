from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

from .lmstudio import LMStudioClient
from .model_identity import resolve_model_strict
from .parsing import answer_candidate_logprobs, exact_one_letter, parse_mcq_letter
from .policy import answer_gap
from .prompts import canonical_from_displayed, core_messages, verifier_messages
from .util import append_jsonl, read_jsonl, sha256_text, stable_seed

CORE = ("B0", "B5", "D0", "D5")


def verifier_orders(base_seed: int, qid: str) -> tuple[list[int], list[int]]:
    orders: list[list[int]] = []
    for label in ("V1", "V2"):
        r = random.Random(stable_seed(base_seed, qid, label))
        order = [0, 1, 2, 3]
        r.shuffle(order)
        if order == [0, 1, 2, 3]:
            order = order[1:] + order[:1]
        if orders and order == orders[0]:
            order = order[1:] + order[:1]
            if order == [0, 1, 2, 3]:
                order = order[1:] + order[:1]
        orders.append(order)
    return orders[0], orders[1]


def _call(client: LMStudioClient, cfg: dict[str, Any], model: str, messages: list[dict[str, str]], seed: int) -> dict[str, Any]:
    retries = int(cfg.get("transport_retries", 2))
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return client.generate(
                str(cfg.get("transport", "responses")),
                model=model,
                messages=messages,
                temperature=float(cfg.get("temperature", 0.0)),
                top_p=float(cfg.get("top_p", 1.0)),
                max_tokens=int(cfg.get("max_tokens", 32)),
                seed=seed,
                top_logprobs=int(cfg.get("top_logprobs", 20)),
                presence_penalty=float(cfg.get("presence_penalty", 0.0)),
                frequency_penalty=float(cfg.get("frequency_penalty", 0.0)),
            )
        except Exception as exc:
            last = exc
            if attempt < retries:
                time.sleep(0.25 * (attempt + 1))
    assert last is not None
    raise last


def _generate_record(client: LMStudioClient, cfg: dict[str, Any], model: str, item: dict[str, Any], condition: str, messages: list[dict[str, str]], seed: int, model_snapshot_sha256: str, *, order: list[int] | None = None) -> dict[str, Any]:
    response = _call(client, cfg, model, messages, seed)
    raw = response.get("text") or ""
    parsed_display = parse_mcq_letter(raw)
    format_retry_used = False
    if bool(cfg.get("format_retry", True)) and not exact_one_letter(raw):
        format_retry_used = True
        retry_messages = list(messages) + [{"role": "user", "content": "Format reminder: Reply with exactly one letter: A, B, C, or D."}]
        response = _call(client, cfg, model, retry_messages, seed)
        raw = response.get("text") or ""
        parsed_display = parse_mcq_letter(raw)
        messages = retry_messages

    canonical = canonical_from_displayed(parsed_display, order) if order is not None else parsed_display
    cands = answer_candidate_logprobs(response.get("token_logprobs"))
    # Verifier candidate logprobs are display-space and are not used as the routing sensor.
    return {
        "schema_version": "ccrc.i5gated.run.v0.6.0",
        "run_key": f"{item['question_id']}:{condition}",
        "question_id": item["question_id"],
        "source_id": item["source_id"],
        "subject": item["subject"],
        "condition": condition,
        "correct_answer": item["correct_answer"],
        "i5_enabled": condition in {"B5", "D5"},
        "prior_answer_visible": False,
        "verifier": condition in {"V1", "V2"},
        "option_order": order,
        "prompt_sha256": sha256_text(str(messages)),
        "messages": messages,
        "raw_output": raw,
        "parsed_display_answer": parsed_display,
        "parsed_answer": canonical,
        "exact_format": exact_one_letter(raw),
        "format_retry_used": format_retry_used,
        "model_call_count": 2 if format_retry_used else 1,
        "candidate_logprobs": cands,
        "sensor_gap": None if order is not None else answer_gap(cands),
        "model": (response.get("meta") or {}).get("model"),
        "model_snapshot_sha256": model_snapshot_sha256,
        "reasoning_detected": bool(response.get("reasoning_detected")),
        "reasoning_tokens": response.get("reasoning_tokens"),
        "request_meta": response.get("request_meta"),
        "usage": response.get("usage"),
        "latency_s": response.get("latency_s"),
        "seed": seed,
    }


def run_experiment(cfg: dict[str, Any], items: list[dict[str, Any]], out_path: Path, *, limit: int | None = None) -> dict[str, Any]:
    client = LMStudioClient(str(cfg["lmstudio_base_url"]), timeout_s=float(cfg.get("timeout_s", 120)))
    model, identity = resolve_model_strict(client, cfg)
    snapshot = str(identity.get("model_snapshot_sha256"))
    required = ((cfg.get("runtime") or {}).get("required_snapshot_sha256"))
    if required and snapshot != required:
        raise RuntimeError(f"Runtime snapshot mismatch: required={required}, observed={snapshot}")

    existing = {r.get("run_key"): r for r in read_jsonl(out_path)}
    selected = items[:limit] if limit is not None else items
    base_seed = int(cfg["seed"])
    max_theta = max(float(x) for x in (cfg.get("controller") or {}).get("thresholds", [0.20, 0.50]))

    for item in selected:
        qid = item["question_id"]
        conditions = list(CORE)
        random.Random(stable_seed(base_seed, qid, "condition_order")).shuffle(conditions)
        for condition in conditions:
            key = f"{qid}:{condition}"
            if key in existing:
                continue
            i5 = condition in {"B5", "D5"}
            blind = condition in {"D0", "D5"}
            messages = core_messages(item, i5=i5, blind=blind)
            seed = stable_seed(base_seed, qid, "B" if condition.startswith("B") else "D")
            record = _generate_record(client, cfg, model, item, condition, messages, seed, snapshot)
            append_jsonl(out_path, record)
            existing[key] = record

        b0, b5, d0, d5 = (existing.get(f"{qid}:{c}") for c in CORE)
        needs_v = False
        for b, d in ((b0, d0), (b5, d5)):
            if not b or not d:
                continue
            gap = b.get("sensor_gap")
            if (gap is None or float(gap) < max_theta) and isinstance(b.get("parsed_answer"), str) and b.get("parsed_answer") in "ABCD" and isinstance(d.get("parsed_answer"), str) and d.get("parsed_answer") in "ABCD" and b.get("parsed_answer") != d.get("parsed_answer"):
                needs_v = True
        if needs_v:
            o1, o2 = verifier_orders(base_seed, qid)
            for label, order in (("V1", o1), ("V2", o2)):
                key = f"{qid}:{label}"
                if key in existing:
                    continue
                messages = verifier_messages(item, order)
                seed = stable_seed(base_seed, qid, label)
                record = _generate_record(client, cfg, model, item, label, messages, seed, snapshot, order=order)
                append_jsonl(out_path, record)
                existing[key] = record

    return {"items_requested": len(selected), "runs_total": len(existing), "model_snapshot_sha256": snapshot}
