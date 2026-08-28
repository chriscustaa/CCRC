from __future__ import annotations

from pathlib import Path
from typing import Any

from .lmstudio import LMStudioClient
from .model_identity import resolve_model_strict
from .parsing import exact_one_letter, parse_mcq_letter
from .prompts import baseline_messages, followup_messages, format_question_prompt
from .util import canonical_json, sha256_text, stable_seed, write_json


def _compact_result(result: dict[str, Any], messages: list[dict[str, str]]) -> dict[str, Any]:
    text = result.get("text") or ""
    return {
        "messages": messages,
        "prompt_sha256": sha256_text(canonical_json(messages)),
        "raw_output": text,
        "parsed": parse_mcq_letter(text),
        "format_compliant": exact_one_letter(text),
        "has_token_logprobs": bool(result.get("token_logprobs")),
        "token_logprobs": result.get("token_logprobs"),
        "usage": result.get("usage"),
        "reasoning_tokens": result.get("reasoning_tokens"),
        "reasoning_content_present": result.get("reasoning_content_present"),
        "reasoning_detected": result.get("reasoning_detected"),
        "transport_request_meta": result.get("request_meta"),
        "transport_response_meta": result.get("meta"),
    }


def run_transport_check(
    cfg: dict[str, Any],
    items: list[dict[str, Any]],
    experiment_dir: Path,
    n_items: int = 2,
) -> dict[str, Any]:
    client = LMStudioClient(
        cfg["lmstudio_base_url"], timeout_s=float(cfg.get("timeout_s", 120))
    )
    model_id, model_info = resolve_model_strict(client, cfg)
    pairs = []

    for item in items[:n_items]:
        qprompt = format_question_prompt(item["question"], item["options"])
        # Use ground truth only for this transport sanity check so endpoint A's own
        # output cannot alter endpoint B's multi-turn input.
        target = next(x for x in "ABCD" if x != item["correct"])
        cases = [
            ("baseline", baseline_messages(qprompt)),
            ("review_fixed_history", followup_messages(qprompt, item["correct"], "R1", target)),
        ]
        for case, messages in cases:
            seed = stable_seed(int(cfg["seed"]), item["source_id"], case, "transport")
            common = dict(
                model=model_id,
                messages=messages,
                temperature=float(cfg.get("temperature", 0.0)),
                top_p=float(cfg.get("top_p", 1.0)),
                max_tokens=int(cfg.get("max_tokens", 128)),
                seed=seed,
                presence_penalty=float(cfg.get("presence_penalty", 0.0)),
                frequency_penalty=float(cfg.get("frequency_penalty", 0.0)),
            )
            chat = responses = None
            chat_error = responses_error = None
            try:
                chat = client.chat(**common)
            except Exception as exc:
                chat_error = str(exc)
            try:
                responses = client.responses(
                    **common, top_logprobs=int(cfg.get("top_logprobs", 20))
                )
            except Exception as exc:
                responses_error = str(exc)

            cc = _compact_result(chat, messages) if chat else None
            rc = _compact_result(responses, messages) if responses else None
            pairs.append({
                "question_id": item["source_id"],
                "case": case,
                "chat": cc,
                "responses": rc,
                "chat_error": chat_error,
                "responses_error": responses_error,
                "parsed_agree": (
                    cc is not None and rc is not None
                    and cc["parsed"] is not None
                    and cc["parsed"] == rc["parsed"]
                ),
                "exact_raw_agree": (
                    cc is not None and rc is not None
                    and cc["raw_output"] == rc["raw_output"]
                ),
            })

    endpoint_failures = sum(1 for p in pairs if not p["chat"] or not p["responses"])
    parsed_disagreements = sum(
        1 for p in pairs
        if p["chat"] and p["responses"] and not p["parsed_agree"]
    )
    responses_without_logprobs = sum(
        1 for p in pairs
        if p["responses"] and not p["responses"]["has_token_logprobs"]
    )
    reasoning_detected = sum(
        1 for p in pairs
        for branch in ("chat", "responses")
        if p.get(branch) and p[branch].get("reasoning_detected")
    )
    raw_disagreements = sum(
        1 for p in pairs
        if p["chat"] and p["responses"] and not p["exact_raw_agree"]
    )

    blocking = []
    if endpoint_failures:
        blocking.append(f"{endpoint_failures} endpoint pair(s) failed")
    if parsed_disagreements:
        blocking.append(f"{parsed_disagreements} parsed-answer disagreement(s)")
    if bool(cfg.get("require_responses_logprobs", True)) and responses_without_logprobs:
        blocking.append(f"{responses_without_logprobs} Responses call(s) lacked logprobs")
    if bool(cfg.get("require_reasoning_off", False)) and reasoning_detected:
        blocking.append(f"{reasoning_detected} call(s) emitted reasoning")

    report = {
        "schema_version": "ccrc.review160.transport_check.v0.4.0",
        "experiment_id": cfg["experiment_id"],
        "model_id": model_id,
        "model_listing": model_info,
        "n_items": n_items,
        "n_pairs": len(pairs),
        "status": "PASS" if not blocking else "BLOCK",
        "blocking_reasons": blocking,
        "warnings": (
            [f"{raw_disagreements} raw-text disagreement(s) with parsed agreement"]
            if raw_disagreements and not parsed_disagreements else []
        ),
        "counts": {
            "endpoint_failures": endpoint_failures,
            "parsed_disagreements": parsed_disagreements,
            "responses_without_logprobs": responses_without_logprobs,
            "reasoning_detected": reasoning_detected,
            "raw_disagreements": raw_disagreements,
        },
        "pairs": pairs,
        "interpretation": "Transport/serialization sanity check only; experimental collection remains on Responses.",
    }
    write_json(experiment_dir / "transport_check.json", report)
    return report
