from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
from pathlib import Path
from typing import Any

import requests
import platform
import os
from datetime import datetime, timezone

from . import __version__
from .dataset import PINNED_DATASET_URL, canonical_stem, load_questions, select_balanced_unique_excluding
from .lmstudio import LMStudioClient
from .runner import run_review160
from .model_identity import (
    ModelIdentityError,
    build_identity_report,
    resolve_model_strict,
)
from .summary import summarize
from .targets import assign_balanced_targets
from .prompts import prompt_audit
from .finalize import finalize_experiment
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
        "schema_version": "ccrc.review160.doctor.v0.4.0",
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
        required_runtime = ((cfg.get("heldout") or {}).get("required_runtime_snapshot_sha256"))
        report["required_runtime_snapshot_sha256"] = required_runtime
        report["runtime_snapshot_matches_prior_qwen35"] = (
            required_runtime is None or identity.get("model_snapshot_sha256") == required_runtime
        )
        if required_runtime and identity.get("model_snapshot_sha256") != required_runtime:
            report["status"] = "BLOCK"
            report["blocking_reasons"] = [
                "Loaded Qwen3.5 runtime snapshot differs from the completed native Qwen3.5 run. "
                f"required={required_runtime}, observed={identity.get('model_snapshot_sha256')}"
            ]
            write_json(Path(args.out), report)
            print(json.dumps(report, indent=2))
            return 2
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
            raise SystemExit("Prepare blocked: doctor.json is missing; run doctor first.")
        doctor = read_json(doctor_path)
        if doctor.get("status") != "PASS":
            raise SystemExit("Prepare blocked: doctor.json status is not PASS.")
        if doctor.get("harness_version") != __version__:
            raise SystemExit("Prepare blocked: doctor harness version differs; rerun doctor.")
        if doctor.get("configured_model_id") != cfg.get("model_id"):
            raise SystemExit("Prepare blocked: config model_id differs from passed doctor.")

    client = LMStudioClient(
        cfg["lmstudio_base_url"], timeout_s=float(cfg.get("timeout_s", 120))
    )
    try:
        model_id, identity = resolve_model_strict(client, cfg)
    except ModelIdentityError as exc:
        raise SystemExit(str(exc)) from exc

    heldout = cfg.get("heldout") or {}
    required_exclude_sha = heldout.get("exclude_items_sha256")
    if not args.exclude_items:
        raise SystemExit(
            "Prepare blocked: --exclude-items must point to the finalized Decomp30 items.jsonl."
        )
    exclude_path = Path(args.exclude_items)
    if not exclude_path.exists():
        raise SystemExit(f"Excluded-items file not found: {exclude_path}")
    observed_exclude_sha = sha256_file(exclude_path)
    if required_exclude_sha and observed_exclude_sha != required_exclude_sha:
        raise SystemExit(
            "Prepare blocked: excluded-items SHA-256 does not match the frozen prior 30. "
            f"expected={required_exclude_sha}, observed={observed_exclude_sha}"
        )
    excluded = read_jsonl(exclude_path)
    if len(excluded) != 30:
        raise SystemExit(f"Prepare blocked: expected 30 excluded prior items, observed {len(excluded)}")
    write_jsonl(out / "excluded_items.jsonl", excluded)

    source_path = Path(args.questions) if args.questions else out / "upstream_questions.json"
    source_origin = "local"
    if not args.questions:
        _download_dataset(source_path)
        source_origin = PINNED_DATASET_URL
    questions = load_questions(source_path)

    exclude_ids = {x["source_id"] for x in excluded}
    exclude_stems = {canonical_stem(x["question"]) for x in excluded}
    n = int(args.n)
    selected = select_balanced_unique_excluding(
        questions, n, int(cfg["seed"]),
        exclude_ids=exclude_ids,
        exclude_stems=exclude_stems,
    )
    write_jsonl(out / "items.jsonl", selected)

    targets = assign_balanced_targets(selected, int(cfg["seed"]))
    write_jsonl(out / "targets.jsonl", targets)
    write_json(out / "prompt_audit.json", {
        "schema_version": "ccrc.review160.prompt_audit.v0.4.0",
        "rows": prompt_audit(),
    })

    package_root = Path(__file__).resolve().parents[1]
    manifest = {
        "schema_version": "ccrc.review160.manifest.v0.4.0",
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
        "heldout_selection": {
            "n": len(selected),
            "seed": int(cfg["seed"]),
            "algorithm": "capacity-proportional domain/difficulty stratification over unique semantic stems after exact prior-ID/stem exclusion",
            "excluded_items_path_at_prepare": str(exclude_path),
            "excluded_items_sha256": observed_exclude_sha,
            "excluded_count": len(excluded),
            "source_experiment_id": heldout.get("exclude_experiment_id"),
            "selected_items_sha256": sha256_file(out / "items.jsonl"),
            "overlap_source_ids": sorted(exclude_ids & {x["source_id"] for x in selected}),
            "unique_semantic_stems": len({canonical_stem(x["question"]) for x in selected}),
            "domain_counts": dict(sorted(Counter(x["domain"] for x in selected).items())),
            "difficulty_counts": dict(sorted(Counter(x["difficulty"] for x in selected).items())),
        },
        "planned_model": {
            "description": "Qwen3.5 9B GGUF Q4_K_M, non-thinking held-out review/M5 screen",
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
            "stateful_responses_continuation": False,
            "logit_bias": None,
        },
        "review_design": {
            "initial_condition": "B: one actual model baseline answer generated once per question",
            "shared_prefix": "all followups use the same frozen parsed B answer; no ground-truth answer is injected",
            "conditions": ["F", "R0", "R1", "R2", "R3", "P", "V"],
            "contrasts": {
                "plain_review": "R0-F",
                "accountability_increment": "R1-R0",
                "anticipated_audit_increment": "R2-R0",
                "additional_consideration_increment": "R3-R0",
                "neutral_wording_sham": "P-F",
                "wrong_verdict": "V-F",
            },
            "review_endpoints": [
                "baseline-wrong to correct repair rate",
                "baseline-correct to wrong harm rate",
                "net revision utility = repair rate - harm rate",
                "paired accuracy change",
                "correct-answer logprob margin",
            ],
        },
        "offline_m5_preregistration": {
            "gamma": 1.0,
            "gamma_tuning_allowed": False,
            "primary": "M5_FV = logp_F + (logp_F - logp_V)",
            "sham": "M5_FP = logp_F + (logp_F - logp_P)",
            "primary_endpoint": "paired A/B/C/D argmax accuracy(M5_FV) - accuracy(F)",
            "mandatory_comparator": "M5_FV must outperform M5_FP, not merely F",
            "harms": "F-correct -> guided-wrong",
            "repairs": "F-wrong -> guided-correct",
            "promotion_rule": (
                "Live token-level M5 remains blocked unless verdict-derived M5 improves held-out "
                "accuracy with low overshoot and beats the neutral-paraphrase sham."
            ),
        },
        "stage_boundary": (
            "Held-out constructive-review and offline M5 validation only. "
            "No live contrastive decoding, gamma tuning, activation steering, or probe training."
        ),
    }
    write_json(out / "manifest.json", manifest)
    refresh_hash_file(out)
    print(f"Prepared {len(selected)} fresh held-out items in {out}")
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

def cmd_run_review(args: argparse.Namespace) -> int:
    cfg = load_cfg(Path(args.config))
    exp = Path(args.experiment)
    if (exp / "FINALIZED.json").exists():
        raise SystemExit("Run blocked: experiment is finalized; create a new experiment version.")

    manifest = read_json(exp / "manifest.json")
    if manifest.get("experiment_id") != cfg.get("experiment_id"):
        raise SystemExit("Config experiment_id does not match frozen manifest.")
    if ((manifest.get("planned_model") or {}).get("transport")) != cfg.get("transport"):
        raise SystemExit("Config transport differs from frozen manifest.")
    if ((manifest.get("planned_model") or {}).get("model_id")) != cfg.get("model_id"):
        raise SystemExit("Config model_id differs from frozen manifest.")

    client = LMStudioClient(
        cfg["lmstudio_base_url"], timeout_s=float(cfg.get("timeout_s", 120))
    )
    try:
        _, live_identity = resolve_model_strict(client, cfg)
    except ModelIdentityError as exc:
        raise SystemExit(str(exc)) from exc
    frozen_snapshot = (manifest.get("planned_model") or {}).get("observed_snapshot_sha256")
    if live_identity.get("model_snapshot_sha256") != frozen_snapshot:
        raise SystemExit("Run blocked: loaded model/runtime snapshot differs from frozen manifest.")

    if not args.limit and bool(cfg.get("require_transport_check_for_full_run", True)):
        tc_path = exp / "transport_check.json"
        if not tc_path.exists() or read_json(tc_path).get("status") != "PASS":
            raise SystemExit("Full run blocked: transport-check must PASS first.")

    items = read_jsonl(exp / "items.jsonl")
    targets = read_jsonl(exp / "targets.jsonl")
    if not items or not targets:
        raise SystemExit("Missing items/targets; run prepare first.")

    run_review160(
        cfg, items, targets, exp,
        limit=int(args.limit) if args.limit else None,
    )
    refresh_hash_file(exp)
    print(f"Run complete: {exp / 'runs.jsonl'}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    exp = Path(args.experiment)
    result = validate_experiment(exp, require_full=bool(getattr(args, 'full', False)))
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 2


def cmd_summarize(args: argparse.Namespace) -> int:
    exp = Path(args.experiment)
    result = summarize(exp)
    refresh_hash_file(exp)
    print(json.dumps(result, indent=2))
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    exp = Path(args.experiment)
    summarize(exp)
    result = finalize_experiment(exp)
    print(json.dumps(result, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ccrc-review160")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor")
    d.add_argument("--config", required=True)
    d.add_argument("--out", required=True)
    d.set_defaults(func=cmd_doctor)

    pr = sub.add_parser("prepare")
    pr.add_argument("--config", required=True)
    pr.add_argument("--out", required=True)
    pr.add_argument("--questions")
    pr.add_argument("--exclude-items", required=True)
    pr.add_argument("--n", type=int, default=160)
    pr.set_defaults(func=cmd_prepare)

    tc = sub.add_parser("transport-check")
    tc.add_argument("--config", required=True)
    tc.add_argument("--experiment", required=True)
    tc.add_argument("--n-items", type=int, default=2)
    tc.set_defaults(func=cmd_transport_check)

    rn = sub.add_parser("run-review")
    rn.add_argument("--config", required=True)
    rn.add_argument("--experiment", required=True)
    rn.add_argument("--limit", type=int)
    rn.set_defaults(func=cmd_run_review)

    v = sub.add_parser("validate")
    v.add_argument("--experiment", required=True)
    v.add_argument("--full", action="store_true")
    v.set_defaults(func=cmd_validate)

    s = sub.add_parser("summarize")
    s.add_argument("--experiment", required=True)
    s.set_defaults(func=cmd_summarize)

    f = sub.add_parser("finalize")
    f.add_argument("--experiment", required=True)
    f.set_defaults(func=cmd_finalize)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
