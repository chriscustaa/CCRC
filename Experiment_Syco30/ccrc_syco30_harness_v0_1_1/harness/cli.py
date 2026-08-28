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
from .runner import resolve_model_id, run_native
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
        "schema_version": "ccrc.syco30.doctor.v0.1.1",
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
        model_id, _ = resolve_model_id(client, cfg.get("model_id"))
        report["resolved_model_id"] = model_id
    except Exception as exc:
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
    )

    try:
        r = client.chat(**common)
        report["checks"]["chat"] = {
            "ok": True,
            "text": r["text"],
            "meta": r["meta"],
            "usage": r["usage"],
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
            "request_meta": r.get("request_meta"),
        }
    except Exception as exc:
        report["checks"]["responses"] = {"ok": False, "error": str(exc)}

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
    report["full_run_preflight"] = {
        "responses_available": responses_ok,
        "responses_logprobs_available": responses_lp,
        "ready_for_primary_transport": (
            responses_ok
            and (responses_lp or not bool(cfg.get("require_responses_logprobs", True)))
        ),
        "action_if_not_ready": (
            None
            if responses_ok and responses_lp
            else "Update LM Studio and the llama.cpp runtime, reload the model, and rerun doctor."
        ),
    }

    write_json(Path(args.out), report)
    print(json.dumps(report, indent=2))
    return 0


def _download_dataset(dest: Path) -> None:
    r = requests.get(PINNED_DATASET_URL, timeout=60)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)


def cmd_prepare(args: argparse.Namespace) -> int:
    cfg = load_cfg(Path(args.config))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    source_path = Path(args.questions) if args.questions else out / "upstream_questions.json"
    source_origin = "local"
    if not args.questions:
        _download_dataset(source_path)
        source_origin = PINNED_DATASET_URL

    questions = load_questions(source_path)
    selected = select_balanced_unique(questions, int(args.n), int(cfg["seed"]))
    write_jsonl(out / "items.jsonl", selected)

    package_root = Path(__file__).resolve().parents[1]
    manifest = {
        "schema_version": "ccrc.syco30.manifest.v0.1.1",
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
            "algorithm": "domain-quota + within-domain difficulty quota + exact-stem dedupe",
        },
        "planned_model": {
            "description": "Qwen 2.5 7B Instruct GGUF Q4_K_M",
            "model_id": cfg.get("model_id"),
            "transport": cfg.get("transport", "responses"),
            "temperature": cfg.get("temperature", 0.0),
            "top_p": cfg.get("top_p", 1.0),
            "top_logprobs": cfg.get("top_logprobs", 20),
            "max_tokens": cfg.get("max_tokens", 128),
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
        "stage_boundary": "Native SycoBench measurement only; no M5 or custom CCRC interventions.",
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
