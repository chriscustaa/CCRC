from __future__ import annotations

import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from . import __version__
from .lmstudio import LMStudioClient
from .model_identity import build_identity_report
from .parsing import exact_one_letter, parse_mcq_letter
from .util import write_json


PROBE_MESSAGES = [{
    "role": "user",
    "content": (
        "Solve the question independently from scratch before finalizing. "
        "Return exactly one letter: A, B, C, or D. Do not include any other text.\n\n"
        "Which number is even?\n\nA) 3\nB) 4\nC) 5\nD) 7\n\n"
        "Answer with exactly one letter: A, B, C, or D. Do not include any other text."
    ),
}]

REASONING_PROBES = [
    "Which product is larger? A) 17*23 B) 19*20. Answer exactly A or B.",
    "If all bloops are razzies and no razzies are tazzies, can any bloop be a tazzy? A) Yes B) No. Answer exactly A or B.",
    "Which fraction is larger? A) 17/31 B) 18/33. Answer exactly A or B.",
]


def run_doctor(cfg: dict[str, Any], out: Path) -> dict[str, Any]:
    client = LMStudioClient(cfg["lmstudio_base_url"], timeout_s=float(cfg.get("timeout_s", 120)))
    identity = build_identity_report(client, cfg)
    blocking = list(identity.get("blocking_reasons") or [])
    required_snapshot = cfg.get("required_runtime_snapshot_sha256")
    if required_snapshot and identity.get("model_snapshot_sha256") != required_snapshot:
        blocking.append(
            "Loaded runtime snapshot differs from the frozen Qwen3.5 lineage runtime: "
            f"required={required_snapshot}, observed={identity.get('model_snapshot_sha256')}"
        )

    probe: dict[str, Any] = {}
    reasoning_probes: list[dict[str, Any]] = []
    model_id = cfg.get("model_id")
    if not blocking and model_id:
        try:
            result = client.responses(
                model=model_id,
                messages=PROBE_MESSAGES,
                temperature=float(cfg.get("temperature", 0.0)),
                top_p=float(cfg.get("top_p", 1.0)),
                max_tokens=int(cfg.get("max_tokens", 128)),
                seed=int(cfg["seed"]),
                top_logprobs=int(cfg.get("top_logprobs", 20)),
                presence_penalty=float(cfg.get("presence_penalty", 0.0)),
                frequency_penalty=float(cfg.get("frequency_penalty", 0.0)),
            )
            raw = result.get("text") or ""
            probe = {
                "ok": True,
                "raw_output": raw,
                "parsed": parse_mcq_letter(raw),
                "exact_format": exact_one_letter(raw),
                "has_logprobs": bool(result.get("token_logprobs")),
                "reasoning_detected": result.get("reasoning_detected"),
                "request_meta": result.get("request_meta"),
                "response_meta": result.get("meta"),
            }
            if probe["parsed"] != "B" or not probe["exact_format"]:
                blocking.append("Verifier-format probe did not return exact correct letter B")
            if bool(cfg.get("require_responses_logprobs", True)) and not probe["has_logprobs"]:
                blocking.append("Responses probe did not return token logprobs")
            if bool(cfg.get("require_reasoning_off", True)) and probe["reasoning_detected"]:
                blocking.append("Responses probe emitted reasoning telemetry")
            if (result.get("meta") or {}).get("model") != model_id:
                blocking.append("Responses endpoint routed to a different model id")
        except Exception as exc:
            probe = {"ok": False, "error": str(exc)}
            blocking.append(f"Responses verifier probe failed: {exc}")

        if bool(cfg.get("require_reasoning_off", True)):
            for i, text in enumerate(REASONING_PROBES):
                try:
                    result = client.responses(
                        model=model_id,
                        messages=[{"role": "user", "content": text}],
                        temperature=float(cfg.get("temperature", 0.0)),
                        top_p=float(cfg.get("top_p", 1.0)),
                        max_tokens=32,
                        seed=int(cfg["seed"]) + 9000 + i,
                        top_logprobs=int(cfg.get("top_logprobs", 20)),
                        presence_penalty=float(cfg.get("presence_penalty", 0.0)),
                        frequency_penalty=float(cfg.get("frequency_penalty", 0.0)),
                    )
                    row = {
                        "ok": True,
                        "prompt": text,
                        "raw_output": result.get("text"),
                        "reasoning_tokens": result.get("reasoning_tokens"),
                        "reasoning_content_present": result.get("reasoning_content_present"),
                        "reasoning_detected": result.get("reasoning_detected"),
                        "response_model": (result.get("meta") or {}).get("model"),
                    }
                    reasoning_probes.append(row)
                    if row["reasoning_detected"]:
                        blocking.append(f"Reasoning-off probe {i + 1} emitted reasoning telemetry")
                    if row["response_model"] != model_id:
                        blocking.append(f"Reasoning-off probe {i + 1} routed to a different model")
                except Exception as exc:
                    reasoning_probes.append({"ok": False, "prompt": text, "error": str(exc)})
                    blocking.append(f"Reasoning-off probe {i + 1} failed: {exc}")

    report = {
        "schema_version": "ccrc.trajectory100.doctor.v0.9.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "harness_version": __version__,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "requests_version": requests.__version__,
        },
        "authentication": {
            "lm_api_token_present": bool(os.getenv("LM_API_TOKEN")),
            "token_value_recorded": False,
        },
        "model_identity": identity,
        "required_runtime_snapshot_sha256": required_snapshot,
        "responses_probe": probe,
        "reasoning_off_probes": reasoning_probes,
        "status": "PASS" if not blocking else "BLOCK",
        "blocking_reasons": blocking,
    }
    write_json(out, report)
    return report


def run_transport_check(cfg: dict[str, Any], out: Path) -> dict[str, Any]:
    """Two non-experimental calls; never consumed as trajectory cells."""
    client = LMStudioClient(cfg["lmstudio_base_url"], timeout_s=float(cfg.get("timeout_s", 120)))
    identity = build_identity_report(client, cfg)
    blocking = list(identity.get("blocking_reasons") or [])
    required_snapshot = cfg.get("required_runtime_snapshot_sha256")
    if required_snapshot and identity.get("model_snapshot_sha256") != required_snapshot:
        blocking.append("Runtime snapshot mismatch")
    fixtures = [
        ("even-number", PROBE_MESSAGES),
        ("capital-france", [{
            "role": "user",
            "content": (
                "Solve the question independently from scratch before finalizing. "
                "Return exactly one letter: A, B, C, or D. Do not include any other text.\n\n"
                "What is the capital of France?\n\nA) Rome\nB) Madrid\nC) Paris\nD) Berlin\n\n"
                "Answer with exactly one letter: A, B, C, or D. Do not include any other text."
            ),
        }]),
    ]
    rows = []
    for i, (name, messages) in enumerate(fixtures):
        try:
            result = client.responses(
                model=str(cfg.get("model_id")), messages=messages,
                temperature=float(cfg.get("temperature", 0.0)),
                top_p=float(cfg.get("top_p", 1.0)), max_tokens=int(cfg.get("max_tokens", 128)),
                seed=int(cfg["seed"]) + 7000 + i,
                top_logprobs=int(cfg.get("top_logprobs", 20)),
                presence_penalty=float(cfg.get("presence_penalty", 0.0)),
                frequency_penalty=float(cfg.get("frequency_penalty", 0.0)),
            )
            raw = result.get("text") or ""
            row = {
                "fixture": name, "ok": True, "raw_output": raw,
                "parsed": parse_mcq_letter(raw), "exact_format": exact_one_letter(raw),
                "reasoning_detected": result.get("reasoning_detected"),
                "has_logprobs": bool(result.get("token_logprobs")),
                "request_meta": result.get("request_meta"), "response_meta": result.get("meta"),
            }
            if not row["exact_format"] or row["parsed"] is None:
                blocking.append(f"Fixture {name} was not exact-format parseable")
            if bool(cfg.get("require_reasoning_off", True)) and row["reasoning_detected"]:
                blocking.append(f"Fixture {name} emitted reasoning")
            rows.append(row)
        except Exception as exc:
            blocking.append(f"Fixture {name} failed: {exc}")
            rows.append({"fixture": name, "ok": False, "error": str(exc)})
    report = {
        "schema_version": "ccrc.trajectory100.transport_check.v0.9.0",
        "experimental_cells_consumed": 0,
        "status": "PASS" if not blocking else "BLOCK",
        "blocking_reasons": blocking,
        "fixtures": rows,
    }
    write_json(out, report)
    return report
