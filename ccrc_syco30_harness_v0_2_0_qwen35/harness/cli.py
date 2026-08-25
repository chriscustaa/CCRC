from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import requests
import platform
import os
from datetime import datetime, timezone

from . import __version__
from .dataset import PINNED_DATASET_URL, load_questions, select_balanced_unique
from .lmstudio import LMStudioClient
from .runner import run_native
from .model_identity import (
    ModelIdentityError,
    build_identity_report,
    resolve_model_strict,
)
from .summary import summarize
from .transport_check import run_transport_check
from .util import (
    read_json,
    read_jsonl,
    refresh_hash_file,
    sha256_file,
    sha256_tree,
    write_json,
    write_jsonl,
)
from .validate import validate_experiment


def load_cfg(path: Path) -> dict[str, Any]:
    cfg = read_json(path)
    required = ["experiment_id", "lmstudio_base_url", "seed"]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise SystemExit(f"Missing config fields: {missing}")
    if cfg.get("transport") not in {"chat", "responses"}:
        raise SystemExit("config.transport must be 'chat' or 'responses'")
    return cfg


def cmd_doctor(args: argparse.Namespace) -> int:
    cfg = load_cfg(Path(args.config))
    client = LMStudioClient(
        cfg["lmstudio_base_url"], timeout_s=float(cfg.get("timeout_s", 120))
    )
    report: dict[str, Any] = {
        "schema_version": "ccrc.syco30.doctor.v0.2.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "harness_version": __version__,
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "requests_version": requests.__version__,
        },
        "base_url": cfg["lmstudio_base_url"],
        "authentication": {
            "lm_api_token_present": bool(os.getenv("LM_API_TOKEN")),
            "token_value_recorded": False
        },
        "configured_model_id": cfg.get("model_id"),
        "checks": {},
    }

    try:
        report["checks"]["openai_models"] = {"ok": True, "data": client.models_openai()}
    except Exception as exc:
        report["checks"]["openai_models"] = {"ok": False, "error": str(exc)}
        write_json(Path(args.out), report)
        print(json.dumps(report, indent=2))
        return 2

    for name, fn in [
        ("native_models_v1", client.models_native_v1),
        ("native_models_v0", client.models_native_v0),
    ]:
        try:
            report["checks"][name] = {"ok": True, "data": fn()}
        except Exception as exc:
            report["checks"][name] = {"ok": False, "error": str(exc)}

    try:
        identity = build_identity_report(client, cfg)
        report["model_identity"] = identity
        if identity["status"] != "PASS":
            report["status"] = "BLOCK"
            report["blocking_reasons"] = identity["blocking_reasons"]
            write_json(Path(args.out), report)
            print(json.dumps(report, indent=2))
            return 2
        model_id = str(identity["configured_model_id"])
        report["resolved_model_id"] = model_id
    except Exception as exc:
        report["status"] = "BLOCK"
        report["model_resolution_error"] = str(exc)
        write_json(Path(args.out), report)
        print(json.dumps(report, indent=2))
        return 2

    test_messages = [{
        "role": "user",
        "content": (
            "Which number is even?\n\nA) 3\nB) 4\nC) 5\nD) 7\n\n"
            "Answer with exactly one letter: A, B, C, or D. Do not include any other text."
        ),
    }]

    common = dict(
        model=model_id,
        messages=test_messages,
        temperature=0.0,
        top_p=1.0,
        max_tokens=4,
        seed=int(cfg["seed"]),
        presence_penalty=float(cfg.get("presence_penalty", 0.0)),
        frequency_penalty=float(cfg.get("frequency_penalty", 0.0)),
    )

    try:
        r = client.chat(**common)
        report["checks"]["chat"] = {
            "ok": True,
            "text": r["text"],
            "meta": r["meta"],
            "usage": r["usage"],
            "reasoning_tokens": r.get("reasoning_tokens"),
            "reasoning_content_present": r.get("reasoning_content_present"),
            "reasoning_detected": r.get("reasoning_detected"),
            "request_meta": r.get("request_meta"),
        }
    except Exception as exc:
        report["checks"]["chat"] = {"ok": False, "error": str(exc)}

    try:
        r = client.responses(**common, top_logprobs=int(cfg.get("top_logprobs", 20)))
        report["checks"]["responses"] = {
            "ok": True,
            "text": r["text"],
            "has_logprobs": bool(r["token_logprobs"]),
            "token_logprobs": r["token_logprobs"],
            "meta": r["meta"],
            "usage": r["usage"],
            "reasoning_tokens": r.get("reasoning_tokens"),
            "reasoning_content_present": r.get("reasoning_content_present"),
            "reasoning_detected": r.get("reasoning_detected"),
            "request_meta": r.get("request_meta"),
        }
    except Exception as exc:
        report["checks"]["responses"] = {"ok": False, "error": str(exc)}

    # Qwen3.5 replication invariant: Thinking must be functionally OFF through the API.
    # Use multiple short reasoning-prone MCQs; require zero reasoning telemetry.
    reasoning_probe_prompts = [
        "Which product is larger? A) 17*23 B) 19*20. Answer exactly A or B.",
        "If all bloops are razzies and no razzies are tazzies, can any bloop be a tazzy? A) Yes B) No. Answer exactly A or B.",
        "Which fraction is larger? A) 17/31 B) 18/33. Answer exactly A or B.",
    ][: int(cfg.get("reasoning_off_probe_count", 3))]
    reasoning_probe = []
    if bool(cfg.get("require_reasoning_off", False)):
        for i, text in enumerate(reasoning_probe_prompts):
            msgs = [{"role": "user", "content": text}]
            try:
                rr = client.responses(
                    model=model_id,
                    messages=msgs,
                    temperature=float(cfg.get("temperature", 0.0)),
                    top_p=float(cfg.get("top_p", 1.0)),
                    max_tokens=32,
                    seed=int(cfg["seed"]) + 9000 + i,
                    top_logprobs=int(cfg.get("top_logprobs", 20)),
                    presence_penalty=float(cfg.get("presence_penalty", 0.0)),
                    frequency_penalty=float(cfg.get("frequency_penalty", 0.0)),
                )
                reasoning_probe.append({
                    "ok": True,
                    "prompt": text,
                    "raw_output": rr.get("text"),
                    "reasoning_tokens": rr.get("reasoning_tokens"),
                    "reasoning_content_present": rr.get("reasoning_content_present"),
                    "reasoning_detected": rr.get("reasoning_detected"),
                    "model": (rr.get("meta") or {}).get("model"),
                })
            except Exception as exc:
                reasoning_probe.append({"ok": False, "prompt": text, "error": str(exc)})
    report["checks"]["reasoning_off_probe"] = reasoning_probe

    chat_text = (report["checks"].get("chat") or {}).get("text")
    resp_text = (report["checks"].get("responses") or {}).get("text")
    report["chat_responses_text_agree"] = (
        chat_text.strip() == resp_text.strip()
        if isinstance(chat_text, str) and isinstance(resp_text, str)
        else None
    )
    responses_ok = bool((report["checks"].get("responses") or {}).get("ok"))
    responses_lp = bool((report["checks"].get("responses") or {}).get("has_logprobs"))
    report["recommended_transport"] = (
        "responses" if responses_ok and responses_lp else "chat"
    )
    chat_model = ((report["checks"].get("chat") or {}).get("meta") or {}).get("model")
    responses_model = ((report["checks"].get("responses") or {}).get("meta") or {}).get("model")
    route_identity_ok = (chat_model == model_id and responses_model == model_id)

    reasoning_probe_ok = True
    if bool(cfg.get("require_reasoning_off", False)):
        rp = report["checks"].get("reasoning_off_probe") or []
        reasoning_probe_ok = bool(rp) and all(
            x.get("ok") and not x.get("reasoning_detected") and x.get("model") == model_id
            for x in rp
        )

    ready = (
        responses_ok
        and (responses_lp or not bool(cfg.get("require_responses_logprobs", True)))
        and bool((report["checks"].get("chat") or {}).get("ok"))
        and route_identity_ok
        and reasoning_probe_ok
    )
    report["full_run_preflight"] = {
        "responses_available": responses_ok,
        "responses_logprobs_available": responses_lp,
        "chat_available": bool((report["checks"].get("chat") or {}).get("ok")),
        "route_identity_ok": route_identity_ok,
        "reasoning_off_probe_ok": reasoning_probe_ok,
        "chat_response_model": chat_model,
        "responses_response_model": responses_model,
        "ready_for_primary_transport": ready,
        "action_if_not_ready": (
            None
            if ready
            else "Resolve endpoint, logprob, or exact model-routing mismatch and rerun doctor."
        ),
    }
    report["status"] = "PASS" if ready else "BLOCK"
    if not ready:
        blocking = []
        if not responses_ok:
            blocking.append("Responses endpoint failed")
        if bool(cfg.get("require_responses_logprobs", True)) and not responses_lp:
            blocking.append("Responses did not expose generated-token logprobs")
        if not bool((report["checks"].get("chat") or {}).get("ok")):
            blocking.append("Chat Completions endpoint failed")
        if not route_identity_ok:
            blocking.append(
                f"endpoint model-routing mismatch: configured={model_id!r}, "
                f"chat={chat_model!r}, responses={responses_model!r}"
            )
        if not reasoning_probe_ok:
            blocking.append("Qwen3.5 reasoning-off probe failed or emitted reasoning")
        report["blocking_reasons"] = blocking

    write_json(Path(args.out), report)
    print(json.dumps(report, indent=2))
    return 0 if ready else 2


def _download_dataset(dest: Path) -> None:
    r = requests.get(PINNED_DATASET_URL, timeout=60)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)


def cmd_prepare(args: argparse.Namespace) -> int:
    cfg = load_cfg(Path(args.config))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if bool(cfg.get("require_doctor_pass_before_prepare", True)):
        doctor_path = out / "doctor.json"
        if not doctor_path.exists():
            raise SystemExit("Prepare blocked: experiment/doctor.json is missing; run doctor first.")
        doctor = read_json(doctor_path)
        if doctor.get("status") != "PASS":
            raise SystemExit("Prepare blocked: doctor.json status is not PASS.")
        if doctor.get("harness_version") != __version__:
            raise SystemExit(
                f"Prepare blocked: doctor harness version {doctor.get('harness_version')!r} "
                f"does not match current harness {__version__!r}; rerun doctor."
            )
        if doctor.get("configured_model_id") != cfg.get("model_id"):
            raise SystemExit("Prepare blocked: config model_id differs from passed doctor.json.")

    client = LMStudioClient(
        cfg["lmstudio_base_url"], timeout_s=float(cfg.get("timeout_s", 120))
    )
    try:
        model_id, identity = resolve_model_strict(client, cfg)
    except ModelIdentityError as exc:
        raise SystemExit(str(exc)) from exc

    replication_cfg = cfg.get("replication") or {}
    require_exact_source = bool(replication_cfg.get("require_exact_source_items", False))
    required_items_sha = replication_cfg.get("required_items_sha256")

    if args.source_items:
        source_items_path = Path(args.source_items)
        if not source_items_path.exists():
            raise SystemExit(f"Replication source items not found: {source_items_path}")
        observed_items_sha = sha256_file(source_items_path)
        if required_items_sha and observed_items_sha != required_items_sha:
            raise SystemExit(
                "Prepare blocked: source-items SHA-256 does not match the frozen Qwen2.5 item set. "
                f"expected={required_items_sha}, observed={observed_items_sha}"
            )
        selected = read_jsonl(source_items_path)
        if len(selected) != 30:
            raise SystemExit(f"Prepare blocked: expected 30 replication items, observed {len(selected)}")
        write_jsonl(out / "items.jsonl", selected)
        source_path = out / "upstream_questions.json"
        source_origin = PINNED_DATASET_URL
        _download_dataset(source_path)
        questions = load_questions(source_path)
        source_items_info = {
            "mode": "exact_replication_items",
            "path_at_prepare": str(source_items_path),
            "sha256": observed_items_sha,
            "source_experiment_id": replication_cfg.get("source_experiment_id"),
        }
    else:
        if require_exact_source:
            raise SystemExit(
                "Prepare blocked: this Qwen3.5 replication profile requires --source-items "
                "pointing to the frozen Qwen2.5 experiment/items.jsonl."
            )
        source_path = Path(args.questions) if args.questions else out / "upstream_questions.json"
        source_origin = "local"
        if not args.questions:
            _download_dataset(source_path)
            source_origin = PINNED_DATASET_URL
        questions = load_questions(source_path)
        selected = select_balanced_unique(questions, int(args.n), int(cfg["seed"]))
        write_jsonl(out / "items.jsonl", selected)
        source_items_info = {"mode": "fresh_selection", "sha256": sha256_file(out / "items.jsonl")}

    package_root = Path(__file__).resolve().parents[1]
    manifest = {
        "schema_version": "ccrc.syco30.manifest.v0.2.0",
        "experiment_id": cfg["experiment_id"],
        "harness": {
            "version": __version__,
            "tree_sha256": sha256_tree(package_root),
        },
        "source": {
            "name": "SycoBench-600",
            "revision": "v1.0.1",
            "origin": source_origin,
            "questions_sha256": sha256_file(source_path),
            "source_count": len(questions),
        },
        "selection": {
            "n": len(selected),
            "seed": int(cfg["seed"]),
            "algorithm": (
                "exact frozen source-items reuse"
                if source_items_info.get("mode") == "exact_replication_items"
                else "domain-quota + within-domain difficulty quota + exact-stem dedupe"
            ),
            "replication_source_items": source_items_info,
        },
        "planned_model": {
            "description": "Qwen3.5 9B GGUF Q4_K_M, non-thinking replication profile",
            "model_id": model_id,
            "expected_profile": identity["expected_model"],
            "observed_snapshot": identity["model_snapshot"],
            "observed_snapshot_sha256": identity["model_snapshot_sha256"],
            "transport": cfg.get("transport", "responses"),
            "temperature": cfg.get("temperature", 0.0),
            "top_p": cfg.get("top_p", 1.0),
            "top_logprobs": cfg.get("top_logprobs", 20),
            "max_tokens": cfg.get("max_tokens", 128),
            "presence_penalty": cfg.get("presence_penalty", 0.0),
            "frequency_penalty": cfg.get("frequency_penalty", 0.0),
            "reasoning_required_off": cfg.get("require_reasoning_off", True),
            "logit_bias": None,
            "stateful_responses_continuation": False,
        },
        "protocol": {
            "upstream": "SycoBench-600 v1.0.1",
            "primary_transport": "responses",
            "comparison_transport": "chat",
            "prompt_hash_scope": "canonical_api_messages_pre_chat_template",
            "format_retry_semantics": "Upstream-compatible: retry output becomes benchmark response; first output remains preserved.",
            "execution_order": "deterministically shuffled question/variant families and follow-up conditions",
        },
        "replication_of": {
            "experiment_id": "syco30-qwen25-7b-q4km-v1",
            "required_items_sha256": "7924a926d70d82e4445633f2da1ecd92d4db44ba2cae6f2f185b795593f23ecb"
        },
        "stage_boundary": "Cross-model native SycoBench replication only; no M5 or custom CCRC interventions.",
    }
    write_json(out / "manifest.json", manifest)
    refresh_hash_file(out)
    print(f"Prepared {len(selected)} frozen items in {out}")
    return 0



def cmd_transport_check(args: argparse.Namespace) -> int:
    cfg = load_cfg(Path(args.config))
    exp = Path(args.experiment)
    items = read_jsonl(exp / "items.jsonl")
    if not items:
        raise SystemExit("No items.jsonl; run prepare first")
    report = run_transport_check(
        cfg,
        items,
        exp,
        n_items=int(args.n_items),
    )
    refresh_hash_file(exp)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 2

def cmd_run_native(args: argparse.Namespace) -> int:
    cfg = load_cfg(Path(args.config))
    exp = Path(args.experiment)

    manifest = read_json(exp / "manifest.json")
    if manifest.get("experiment_id") != cfg.get("experiment_id"):
        raise SystemExit("Config experiment_id does not match frozen manifest.json")
    frozen_transport = ((manifest.get("planned_model") or {}).get("transport"))
    if frozen_transport != cfg.get("transport"):
        raise SystemExit(
            f"Config transport={cfg.get('transport')!r} differs from frozen manifest transport={frozen_transport!r}"
        )

    frozen_model_id = ((manifest.get("planned_model") or {}).get("model_id"))
    if frozen_model_id != cfg.get("model_id"):
        raise SystemExit(
            f"Config model_id={cfg.get('model_id')!r} differs from frozen manifest model_id={frozen_model_id!r}"
        )

    client = LMStudioClient(
        cfg["lmstudio_base_url"], timeout_s=float(cfg.get("timeout_s", 120))
    )
    try:
        _, live_identity = resolve_model_strict(client, cfg)
    except ModelIdentityError as exc:
        raise SystemExit(str(exc)) from exc
    frozen_snapshot_hash = (
        (manifest.get("planned_model") or {}).get("observed_snapshot_sha256")
    )
    if live_identity.get("model_snapshot_sha256") != frozen_snapshot_hash:
        raise SystemExit(
            "Run blocked: loaded model/runtime snapshot no longer matches the frozen manifest. "
            f"frozen={frozen_snapshot_hash}, live={live_identity.get('model_snapshot_sha256')}. "
            "Do not continue; restore the frozen LM Studio load configuration or start a new experiment version."
        )

    # A full run is blocked until the endpoint sanity check passes. Smoke/acceptance
    # runs with --limit remain available for debugging.
    if not args.limit and bool(cfg.get("require_transport_check_for_full_run", True)):
        tc_path = exp / "transport_check.json"
        if not tc_path.exists():
            raise SystemExit("Full run blocked: run transport-check first")
        tc = read_json(tc_path)
        if tc.get("status") != "PASS":
            raise SystemExit(
                "Full run blocked: transport_check.json status is not PASS. "
                "Resolve the reported endpoint/logprob issue before collecting data."
            )

    items = read_jsonl(exp / "items.jsonl")
    if not items:
        raise SystemExit("No items.jsonl; run prepare first")
    run_native(
        cfg,
        items,
        exp,
        variants=int(args.variants),
        limit=int(args.limit) if args.limit else None,
    )
    refresh_hash_file(exp)
    print(f"Run complete: {exp / 'runs.jsonl'}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    exp = Path(args.experiment)
    result = validate_experiment(exp)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 2


def cmd_summarize(args: argparse.Namespace) -> int:
    exp = Path(args.experiment)
    result = summarize(exp)
    refresh_hash_file(exp)
    print(json.dumps(result, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ccrc-syco30")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor")
    d.add_argument("--config", required=True)
    d.add_argument("--out", required=True)
    d.set_defaults(func=cmd_doctor)

    pr = sub.add_parser("prepare")
    pr.add_argument("--config", required=True)
    pr.add_argument("--out", required=True)
    pr.add_argument("--questions")
    pr.add_argument("--source-items")
    pr.add_argument("--n", type=int, default=30)
    pr.set_defaults(func=cmd_prepare)

    tc = sub.add_parser("transport-check")
    tc.add_argument("--config", required=True)
    tc.add_argument("--experiment", required=True)
    tc.add_argument("--n-items", type=int, default=2)
    tc.set_defaults(func=cmd_transport_check)

    rn = sub.add_parser("run-native")
    rn.add_argument("--config", required=True)
    rn.add_argument("--experiment", required=True)
    rn.add_argument("--variants", type=int, default=3)
    rn.add_argument("--limit", type=int)
    rn.set_defaults(func=cmd_run_native)

    v = sub.add_parser("validate")
    v.add_argument("--experiment", required=True)
    v.set_defaults(func=cmd_validate)

    s = sub.add_parser("summarize")
    s.add_argument("--experiment", required=True)
    s.set_defaults(func=cmd_summarize)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
