from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from . import __version__
from .dataset import load_mmlu
from .lmstudio import LMStudioClient
from .model_identity import build_identity_report, resolve_model_strict
from .parsing import answer_candidate_logprobs
from .prompts import prompt_audit
from .runner import run_experiment
from .summary import summarize
from .util import read_json, read_jsonl, refresh_hash_file, sha256_file, write_json, write_jsonl
from .validate import validate


def load_cfg(path: Path) -> dict[str, Any]:
    cfg = read_json(path)
    for key in ("experiment_id", "lmstudio_base_url", "seed"):
        if key not in cfg:
            raise SystemExit(f"Missing config field: {key}")
    return cfg


def doctor(cfg: dict[str, Any]) -> dict[str, Any]:
    client = LMStudioClient(str(cfg["lmstudio_base_url"]), timeout_s=float(cfg.get("timeout_s", 120)))
    identity = build_identity_report(client, cfg)
    report: dict[str, Any] = {"schema_version": "ccrc.i5gated.doctor.v0.6.0", "created_at_utc": datetime.now(timezone.utc).isoformat(), "harness_version": __version__, "model_identity": identity, "checks": {}}
    if identity["status"] != "PASS":
        report["status"] = "BLOCK"; return report
    model = str(identity["configured_model_id"])
    messages = [{"role": "user", "content": "Which number is even?\n\nA) 3\nB) 4\nC) 5\nD) 7\n\nAnswer with exactly one letter: A, B, C, or D. Do not include any other text."}]
    try:
        r = client.responses(model=model, messages=messages, temperature=0.0, top_p=1.0, max_tokens=8, seed=int(cfg["seed"]), top_logprobs=int(cfg.get("top_logprobs", 20)))
        cands = answer_candidate_logprobs(r.get("token_logprobs"))
        report["checks"]["responses"] = {"ok": True, "text": r.get("text"), "candidate_logprobs": cands, "reasoning_detected": r.get("reasoning_detected"), "model": (r.get("meta") or {}).get("model")}
    except Exception as exc:
        report["checks"]["responses"] = {"ok": False, "error": str(exc)}
    check = report["checks"]["responses"]
    required_snapshot = ((cfg.get("runtime") or {}).get("required_snapshot_sha256"))
    snapshot_ok = not required_snapshot or identity.get("model_snapshot_sha256") == required_snapshot
    report["runtime_snapshot_matches_required"] = snapshot_ok
    report["status"] = "PASS" if check.get("ok") and not check.get("reasoning_detected") and all(check.get("candidate_logprobs", {}).get(x) is not None for x in "ABCD") and snapshot_ok else "BLOCK"
    return report


def transport_check(cfg: dict[str, Any]) -> dict[str, Any]:
    client = LMStudioClient(str(cfg["lmstudio_base_url"]), timeout_s=float(cfg.get("timeout_s", 120)))
    model, identity = resolve_model_strict(client, cfg)
    prompts = [
        "Which number is even? A) 3 B) 4 C) 5 D) 7. Answer exactly one letter: A, B, C, or D.",
        "Which fraction is larger? A) 17/31 B) 18/33 C) 1/3 D) 1/4. Answer exactly one letter: A, B, C, or D.",
        "If all bloops are razzies and no razzies are tazzies, can a bloop be a tazzy? A) Yes B) No C) Sometimes D) Unknown. Answer exactly one letter: A, B, C, or D.",
    ]
    rows = []
    for i, text in enumerate(prompts):
        r = client.responses(model=model, messages=[{"role": "user", "content": text}], temperature=0.0, top_p=1.0, max_tokens=8, seed=int(cfg["seed"]) + i, top_logprobs=int(cfg.get("top_logprobs", 20)))
        rows.append({"text": r.get("text"), "candidate_logprobs": answer_candidate_logprobs(r.get("token_logprobs")), "reasoning_detected": r.get("reasoning_detected"), "model": (r.get("meta") or {}).get("model")})
    required_snapshot = ((cfg.get("runtime") or {}).get("required_snapshot_sha256"))
    snapshot_ok = not required_snapshot or identity.get("model_snapshot_sha256") == required_snapshot
    ok = snapshot_ok and all(not x["reasoning_detected"] and x["model"] == model and all(x["candidate_logprobs"].get(l) is not None for l in "ABCD") for x in rows)
    return {"schema_version": "ccrc.i5gated.transport.v0.6.0", "status": "PASS" if ok else "BLOCK", "model_snapshot_sha256": identity.get("model_snapshot_sha256"), "runtime_snapshot_matches_required": snapshot_ok, "checks": rows}


def main() -> int:
    p = argparse.ArgumentParser(prog="ccrc-i5gated")
    sub = p.add_subparsers(dest="cmd", required=True)
    for cmd in ("doctor", "transport-check"):
        sp = sub.add_parser(cmd); sp.add_argument("--config", required=True); sp.add_argument("--out", required=True)
    sp = sub.add_parser("prepare"); sp.add_argument("--config", required=True); sp.add_argument("--experiment-dir", required=True)
    sp = sub.add_parser("run"); sp.add_argument("--config", required=True); sp.add_argument("--experiment-dir", required=True); sp.add_argument("--limit", type=int)
    for cmd in ("summarize", "validate", "finalize"):
        sp = sub.add_parser(cmd); sp.add_argument("--config", required=True); sp.add_argument("--experiment-dir", required=True)
    args = p.parse_args()
    cfg = load_cfg(Path(args.config))

    if args.cmd in {"doctor", "transport-check"}:
        report = doctor(cfg) if args.cmd == "doctor" else transport_check(cfg)
        write_json(Path(args.out), report); print(json.dumps(report, indent=2)); return 0 if report["status"] == "PASS" else 2

    exp = Path(args.experiment_dir); exp.mkdir(parents=True, exist_ok=True)
    if args.cmd == "prepare":
        if (exp / "runs.jsonl").exists() and (exp / "runs.jsonl").stat().st_size > 0:
            raise SystemExit("runs.jsonl already contains outcomes; refusing to re-prepare frozen design")
        doctor_path = exp / "doctor.json"
        if bool(cfg.get("require_doctor_pass_before_prepare", True)) and (not doctor_path.exists() or read_json(doctor_path).get("status") != "PASS"):
            raise SystemExit("doctor PASS required before prepare")
        items, dsmeta = load_mmlu(cfg)
        write_jsonl(exp / "items.jsonl", items)
        audit = prompt_audit(); write_json(exp / "prompt_audit.json", audit)
        manifest = {"schema_version": "ccrc.i5gated.manifest.v0.6.0", "experiment_id": cfg["experiment_id"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "dataset": dsmeta, "selected_items_sha256": sha256_file(exp / "items.jsonl"), "i5_sha256": audit["i5_sha256"], "thresholds": (cfg.get("controller") or {}).get("thresholds", [0.20, 0.50]), "runtime_required_snapshot_sha256": ((cfg.get("runtime") or {}).get("required_snapshot_sha256")), "preregistered_before_outcomes": True}
        write_json(exp / "manifest.json", manifest); refresh_hash_file(exp); print(json.dumps(manifest, indent=2)); return 0

    manifest_path = exp / "manifest.json"
    if not manifest_path.exists():
        raise SystemExit("manifest.json missing; run prepare first")
    manifest = read_json(manifest_path)
    current_audit = prompt_audit()
    if manifest.get("i5_sha256") != current_audit.get("i5_sha256"):
        raise SystemExit("I5 prompt hash differs from frozen manifest; start a new experiment version")
    cfg_thresholds = [float(x) for x in (cfg.get("controller") or {}).get("thresholds", [0.20, 0.50])]
    frozen_thresholds = [float(x) for x in manifest.get("thresholds", [])]
    if cfg_thresholds != frozen_thresholds:
        raise SystemExit(f"Controller thresholds differ from frozen manifest: {cfg_thresholds} != {frozen_thresholds}")
    if sha256_file(exp / "items.jsonl") != manifest.get("selected_items_sha256"):
        raise SystemExit("items.jsonl hash differs from frozen manifest")
    items = read_jsonl(exp / "items.jsonl")
    if args.cmd == "run":
        tc = exp / "transport_check.json"
        if bool(cfg.get("require_transport_check_for_full_run", True)) and args.limit is None and (not tc.exists() or read_json(tc).get("status") != "PASS"):
            raise SystemExit("transport-check PASS required before full run")
        report = run_experiment(cfg, items, exp / "runs.jsonl", limit=args.limit); refresh_hash_file(exp); print(json.dumps(report, indent=2)); return 0

    runs = read_jsonl(exp / "runs.jsonl")
    if args.cmd == "summarize":
        keys = {r.get("run_key") for r in runs}
        missing_core = [f"{item['question_id']}:{condition}" for item in items for condition in ("B0", "B5", "D0", "D5") if f"{item['question_id']}:{condition}" not in keys]
        if missing_core:
            raise SystemExit(f"core matrix incomplete ({len(missing_core)} missing); refusing partial outcome summary")
        precheck = validate(items, runs, cfg, require_full=True)
        if precheck["status"] != "PASS":
            raise SystemExit("validation BLOCK; refusing outcome summary")
        report = summarize(items, runs, cfg); write_json(exp / "summary.json", report); refresh_hash_file(exp); print(json.dumps(report, indent=2)); return 0
    if args.cmd == "validate":
        report = validate(items, runs, cfg, require_full=True); write_json(exp / "validation.json", report); refresh_hash_file(exp); print(json.dumps(report, indent=2)); return 0 if report["status"] == "PASS" else 2
    if args.cmd == "finalize":
        summary = summarize(items, runs, cfg); write_json(exp / "summary.json", summary)
        validation = validate(items, runs, cfg, require_full=True); write_json(exp / "validation.json", validation)
        if validation["status"] != "PASS":
            raise SystemExit("validation BLOCK; not finalizing")
        final = {"schema_version": "ccrc.i5gated.finalized.v0.6.0", "experiment_id": cfg["experiment_id"], "finalized_at_utc": datetime.now(timezone.utc).isoformat(), "status": "PASS", "validation_errors": 0, "validation_warnings": len(validation["warnings"]), "items_sha256": sha256_file(exp / "items.jsonl"), "runs_sha256": sha256_file(exp / "runs.jsonl"), "summary_sha256": sha256_file(exp / "summary.json")}
        write_json(exp / "FINALIZED.json", final); refresh_hash_file(exp); print(json.dumps(final, indent=2)); return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
