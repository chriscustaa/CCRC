from __future__ import annotations

from pathlib import Path
from typing import Any

from .lmstudio import LMStudioClient
from .parsing import exact_one_letter, parse_mcq_letter
from .prompts import baseline_messages, fixed_prefix_messages, format_question_prompt
from .model_identity import resolve_model_strict
from .util import canonical_json, sha256_text, stable_seed, write_json


def _compact_result(result: dict[str, Any], messages: list[dict[str, str]]) -> dict[str, Any]:
    text = result.get("text") or ""
    return {
        "messages": messages,
        "prompt_sha256": sha256_text(canonical_json(messages)),
        "prompt_hash_scope": "canonical_api_messages_pre_chat_template",
        "raw_output": text,
        "parsed": parse_mcq_letter(text),
        "format_compliant": exact_one_letter(text),
        "has_token_logprobs": bool(result.get("token_logprobs")),
        "token_logprobs": result.get("token_logprobs"),
        "usage": result.get("usage"),
        "reasoning_tokens": result.get("reasoning_tokens"),
        "reasoning_content_present": result.get("reasoning_content_present"),
        "reasoning_detected": result.get("reasoning_detected"),
        "latency_s": result.get("latency_s"),
        "transport_request_meta": result.get("request_meta"),
        "transport_response_meta": result.get("meta"),
    }


def run_transport_check(
    cfg: dict[str, Any],
    items: list[dict[str, Any]],
    experiment_dir: Path,
    n_items: int = 2,
) -> dict[str, Any]:
    if len(items) < n_items:
        raise ValueError(f"Need at least {n_items} prepared items")
    client = LMStudioClient(
        cfg["lmstudio_base_url"], timeout_s=float(cfg.get("timeout_s", 120))
    )
    model_id, model_info = resolve_model_strict(client, cfg)

    pairs: list[dict[str, Any]] = []
    # Two prompt shapes per frozen item:
    # 1) baseline;
    # 2) a multi-turn authority follow-up with a *fixed, identical* assistant
    #    history equal to the registered ground-truth letter. This isolates endpoint
    #    serialization/transport rather than allowing each endpoint's own baseline
    #    output to change the follow-up history.
    for item in items[:n_items]:
        qprompt = format_question_prompt(item["question"], item["options"])
        prompt_cases = [
            ("baseline", baseline_messages(qprompt)),
            (
                "authority_fixed_history",
                fixed_prefix_messages(
                    qprompt,
                    item["correct"],
                    "A",
                    0,
                    "A",
                ),
            ),
        ]

        for case_name, messages in prompt_cases:
            seed = stable_seed(int(cfg["seed"]), item["source_id"], case_name, "transport_check")
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

            chat_err = None
            resp_err = None
            chat = None
            responses = None
            try:
                chat = client.chat(**common)
            except Exception as exc:
                chat_err = str(exc)
            try:
                responses = client.responses(
                    **common, top_logprobs=int(cfg.get("top_logprobs", 20))
                )
            except Exception as exc:
                resp_err = str(exc)

            chat_c = _compact_result(chat, messages) if chat else None
            resp_c = _compact_result(responses, messages) if responses else None

            parsed_agree = (
                chat_c is not None
                and resp_c is not None
                and chat_c["parsed"] is not None
                and chat_c["parsed"] == resp_c["parsed"]
            )
            exact_raw_agree = (
                chat_c is not None
                and resp_c is not None
                and chat_c["raw_output"] == resp_c["raw_output"]
            )

            pairs.append({
                "question_id": item["source_id"],
                "task_id": item["task_id"],
                "case": case_name,
                "correct_answer": item["correct"],
                "messages_sha256": sha256_text(canonical_json(messages)),
                "chat": chat_c,
                "responses": resp_c,
                "chat_error": chat_err,
                "responses_error": resp_err,
                "parsed_agree": parsed_agree,
                "exact_raw_agree": exact_raw_agree,
            })

    endpoint_failures = sum(
        1 for p in pairs if p["chat"] is None or p["responses"] is None
    )
    parsed_disagreements = sum(
        1 for p in pairs
        if p["chat"] is not None
        and p["responses"] is not None
        and (
            p["chat"]["parsed"] is None
            or p["responses"]["parsed"] is None
            or p["chat"]["parsed"] != p["responses"]["parsed"]
        )
    )
    raw_disagreements = sum(
        1 for p in pairs
        if p["chat"] is not None
        and p["responses"] is not None
        and p["chat"]["raw_output"] != p["responses"]["raw_output"]
    )
    responses_without_logprobs = sum(
        1 for p in pairs
        if p["responses"] is not None and not p["responses"]["has_token_logprobs"]
    )
    reasoning_detected = sum(
        1 for p in pairs
        for branch in ("chat", "responses")
        if p.get(branch) is not None and p[branch].get("reasoning_detected")
    )
    responses_seed_not_sent = sum(
        1 for p in pairs
        if p["responses"] is not None
        and not (p["responses"].get("transport_request_meta") or {}).get("seed_sent", False)
    )

    require_lp = bool(cfg.get("require_responses_logprobs", True))
    blocking = []
    if endpoint_failures:
        blocking.append(f"{endpoint_failures} endpoint call pair(s) failed")
    if parsed_disagreements:
        blocking.append(f"{parsed_disagreements} parsed-answer disagreement/unparsed pair(s)")
    if require_lp and responses_without_logprobs:
        blocking.append(
            f"{responses_without_logprobs} Responses call(s) lacked generated-token logprobs"
        )
    if bool(cfg.get("require_reasoning_off", False)) and reasoning_detected:
        blocking.append(
            f"{reasoning_detected} transport-check call(s) emitted reasoning despite reasoning-off requirement"
        )

    warnings = []
    if raw_disagreements and not parsed_disagreements:
        warnings.append(
            f"{raw_disagreements} pair(s) differed in raw text but agreed on parsed choice"
        )
    if responses_seed_not_sent:
        warnings.append(
            f"{responses_seed_not_sent} Responses call(s) did not send the requested seed; "
            "temperature=0 remains frozen, and this is recorded in run metadata"
        )

    status = "PASS" if not blocking else "BLOCK"
    report = {
        "schema_version": "ccrc.decomp30.transport_check.v0.3.0",
        "experiment_id": cfg["experiment_id"],
        "model_id": model_id,
        "model_listing": model_info,
        "primary_transport": "responses",
        "comparison_transport": "chat",
        "stateful_responses_continuation_used": False,
        "logit_bias_used": False,
        "n_items": n_items,
        "n_pairs": len(pairs),
        "status": status,
        "blocking_reasons": blocking,
        "warnings": warnings,
        "counts": {
            "endpoint_failures": endpoint_failures,
            "parsed_disagreements": parsed_disagreements,
            "raw_disagreements": raw_disagreements,
            "responses_without_logprobs": responses_without_logprobs,
            "responses_seed_not_sent": responses_seed_not_sent,
            "reasoning_detected": reasoning_detected,
        },
        "interpretation": (
            "This is a transport/serialization sanity check, not evidence that the endpoints "
            "are distributionally identical. Full matched-decomposition collection remains on Responses."
        ),
        "pairs": pairs,
    }
    write_json(experiment_dir / "transport_check.json", report)
    return report
