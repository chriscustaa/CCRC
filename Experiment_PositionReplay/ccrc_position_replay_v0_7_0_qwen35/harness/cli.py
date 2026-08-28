from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .analysis import analyze
from .design import FORMAT_LINE, FORMAT_RETRY, VERIFIER_PREFIX
from .util import read_json, read_jsonl, sha256_file, sha256_text, write_json
from .validate import validate_experiment, verify_frozen

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def load_cfg(path: Path) -> dict[str, Any]:
    cfg = read_json(path)
    required = ["experiment_id", "lmstudio_base_url", "model_id", "seed"]
    missing = [x for x in required if not cfg.get(x)]
    if missing:
        raise SystemExit(f"Missing config values: {missing}")
    if cfg.get("transport", "responses") != "responses":
        raise SystemExit("The frozen replay requires the Responses transport")
    if float(cfg.get("temperature", 0.0)) != 0.0:
        raise SystemExit("temperature must remain frozen at 0")
    if float((cfg.get("routing") or {}).get("theta", 0.20)) != 0.20:
        raise SystemExit("routing.theta must remain frozen at 0.20")
    if float((cfg.get("decision") or {}).get("positive_schedule_fraction", 0.95)) != 0.95:
        raise SystemExit("positive schedule fraction must remain frozen at 0.95")
    return cfg


def assert_config_frozen(cfg: dict[str, Any], manifest: dict[str, Any]) -> None:
    if cfg != manifest.get("config"):
        raise SystemExit(
            "Config differs from the initialized manifest. Restore the frozen config; "
            "do not change decoding, model, thresholds, seeds, or decision rules mid-run."
        )


def refresh_hashes(experiment_dir: Path) -> None:
    targets = [
        "doctor.json", "transport_check.json", "manifest.json", "prompt_audit.json",
        "runs.jsonl", "validation.json", "analysis.json", "cell_results.csv", "FINALIZED.json",
    ]
    lines = []
    for name in targets:
        path = experiment_dir / name
        if path.exists():
            lines.append(f"{sha256_file(path)}  {name}")
    frozen = experiment_dir / "frozen" / "FROZEN_SHA256.txt"
    if frozen.exists():
        lines.append(f"{sha256_file(frozen)}  frozen/FROZEN_SHA256.txt")
    (experiment_dir / "hashes.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def cmd_doctor(args: argparse.Namespace) -> int:
    from .preflight import run_doctor

    report = run_doctor(load_cfg(Path(args.config)), Path(args.out))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


def cmd_init(args: argparse.Namespace) -> int:
    cfg = load_cfg(Path(args.config))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    doctor_path = Path(args.doctor)
    doctor = read_json(doctor_path)
    if doctor.get("status") != "PASS":
        raise SystemExit("Doctor must PASS before initialization")
    if doctor.get("required_runtime_snapshot_sha256") != cfg.get("required_runtime_snapshot_sha256"):
        raise SystemExit("Doctor/config runtime snapshot mismatch")
    doctor_identity = doctor.get("model_identity") or {}
    if doctor_identity.get("configured_model_id") != cfg.get("model_id"):
        raise SystemExit("Doctor/config model_id mismatch")
    frozen_errors = verify_frozen(PACKAGE_ROOT / "frozen")
    if frozen_errors:
        raise SystemExit("Package frozen inputs failed: " + "; ".join(frozen_errors))
    target_frozen = out / "frozen"
    if target_frozen.exists():
        if verify_frozen(target_frozen):
            raise SystemExit("Existing experiment frozen inputs do not verify")
    else:
        shutil.copytree(PACKAGE_ROOT / "frozen", target_frozen)
    shutil.copy2(doctor_path, out / "doctor.json")
    prompt_audit = {
        "schema_version": "ccrc.position_replay.prompt_audit.v0.7.0",
        "verifier_prefix": VERIFIER_PREFIX,
        "format_line": FORMAT_LINE,
        "format_retry": FORMAT_RETRY,
        "verifier_prefix_sha256": sha256_text(VERIFIER_PREFIX),
        "wording_identical_for_R1_R2": True,
        "prior_answer_visible": False,
        "stateful_continuation": False,
    }
    write_json(out / "prompt_audit.json", prompt_audit)
    manifest = {
        "schema_version": "ccrc.position_replay.manifest.v0.7.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "harness_version": __version__,
        "experiment_id": cfg["experiment_id"],
        "preregistered_before_new_verifier_outcomes": True,
        "config": cfg,
        "frozen_input_hash_manifest_sha256": sha256_file(target_frozen / "FROZEN_SHA256.txt"),
        "planned_base_cells": 568,
        "format_retries_may_add_calls": True,
        "policy_constraints": {
            "theta": 0.20,
            "one_R1_and_one_R2_vote_per_escalated_item": True,
            "D0_is_third_vote": True,
            "majority_across_eight_replay_cells_forbidden": True,
            "positive_schedule_fraction_threshold": 0.95,
            "closed_form_expected_net_must_be_positive": True,
        },
    }
    write_json(out / "manifest.json", manifest)
    if not (out / "runs.jsonl").exists():
        (out / "runs.jsonl").touch()
    refresh_hashes(out)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def cmd_transport(args: argparse.Namespace) -> int:
    from .preflight import run_transport_check

    cfg = load_cfg(Path(args.config))
    out = Path(args.out)
    assert_config_frozen(cfg, read_json(out / "manifest.json"))
    report = run_transport_check(cfg, out / "transport_check.json")
    refresh_hashes(out)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


def _load_experiment_inputs(out: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return (
        read_jsonl(out / "frozen" / "replay_items.jsonl"),
        read_jsonl(out / "frozen" / "call_plan.jsonl"),
    )


def cmd_run(args: argparse.Namespace) -> int:
    from .runner import run_replay

    cfg = load_cfg(Path(args.config))
    out = Path(args.out)
    manifest = read_json(out / "manifest.json")
    assert_config_frozen(cfg, manifest)
    if not (out / "transport_check.json").exists() or read_json(out / "transport_check.json").get("status") != "PASS":
        raise SystemExit("Transport check must PASS before experimental cells run")
    items, plan = _load_experiment_inputs(out)
    result = run_replay(cfg, items, plan, out, limit=args.limit)
    refresh_hashes(out)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    report = validate_experiment(Path(args.out), full=args.full)
    refresh_hashes(Path(args.out))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


def cmd_analyze(args: argparse.Namespace) -> int:
    cfg = load_cfg(Path(args.config))
    out = Path(args.out)
    assert_config_frozen(cfg, read_json(out / "manifest.json"))
    report = analyze(out, float((cfg.get("decision") or {})["positive_schedule_fraction"]))
    refresh_hashes(out)
    print(json.dumps(report["primary_decision"], indent=2, sort_keys=True))
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    out = Path(args.out)
    cfg = load_cfg(Path(args.config))
    assert_config_frozen(cfg, read_json(out / "manifest.json"))
    validation = validate_experiment(out, full=True)
    if validation["status"] != "PASS":
        raise SystemExit("Full validation failed; refusing to finalize")
    analysis = analyze(out, float((cfg.get("decision") or {})["positive_schedule_fraction"]))
    final = {
        "schema_version": "ccrc.position_replay.finalized.v0.7.0",
        "finalized_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation_status": validation["status"],
        "planned_base_cells": 568,
        "completed_base_cells": validation["completed_cells"],
        "actual_model_calls": validation["actual_model_calls"],
        "primary_actuator_survives": analysis["primary_decision"]["actuator_survives"],
        "primary_kill_reasons": analysis["primary_decision"]["kill_reasons"],
    }
    write_json(out / "FINALIZED.json", final)
    refresh_hashes(out)
    print(json.dumps(final, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ccrc-position-replay")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("doctor"); p.add_argument("--config", required=True); p.add_argument("--out", required=True); p.set_defaults(func=cmd_doctor)
    p = sub.add_parser("init"); p.add_argument("--config", required=True); p.add_argument("--doctor", required=True); p.add_argument("--out", required=True); p.set_defaults(func=cmd_init)
    p = sub.add_parser("transport-check"); p.add_argument("--config", required=True); p.add_argument("--out", required=True); p.set_defaults(func=cmd_transport)
    p = sub.add_parser("run"); p.add_argument("--config", required=True); p.add_argument("--out", required=True); p.add_argument("--limit", type=int); p.set_defaults(func=cmd_run)
    p = sub.add_parser("validate"); p.add_argument("--out", required=True); p.add_argument("--full", action="store_true"); p.set_defaults(func=cmd_validate)
    p = sub.add_parser("analyze"); p.add_argument("--config", required=True); p.add_argument("--out", required=True); p.set_defaults(func=cmd_analyze)
    p = sub.add_parser("finalize"); p.add_argument("--config", required=True); p.add_argument("--out", required=True); p.set_defaults(func=cmd_finalize)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
