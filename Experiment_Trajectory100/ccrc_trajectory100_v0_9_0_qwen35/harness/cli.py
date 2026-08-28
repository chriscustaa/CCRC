from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .analysis import analyze
from .design import FORMAT_LINE, FORMAT_RETRY, STAGE_INSTRUCTIONS
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
        raise SystemExit("The frozen pilot requires the Responses transport")
    if float(cfg.get("temperature", 0.0)) != 0.0 or float(cfg.get("top_p", 1.0)) != 1.0:
        raise SystemExit("temperature=0 and top_p=1 must remain frozen")
    expected = {"minimum_repairs": 5, "minimum_net": 3, "max_harm_repair_ratio": 0.5}
    if cfg.get("decision") != expected:
        raise SystemExit(f"decision must remain frozen at {expected}")
    return cfg


def assert_config_frozen(cfg: dict[str, Any], manifest: dict[str, Any]) -> None:
    if cfg != manifest.get("config"):
        raise SystemExit("Config differs from the initialized manifest; restore the frozen config")


def refresh_hashes(out: Path) -> None:
    targets = [
        "doctor.json", "transport_check.json", "manifest.json", "prompt_audit.json",
        "runs.jsonl", "validation.json", "analysis.json", "trajectory_items.csv", "FINALIZED.json",
    ]
    lines = [f"{sha256_file(out / name)}  {name}" for name in targets if (out / name).exists()]
    frozen = out / "frozen" / "FROZEN_SHA256.txt"
    if frozen.exists():
        lines.append(f"{sha256_file(frozen)}  frozen/FROZEN_SHA256.txt")
    (out / "hashes.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def cmd_doctor(args: argparse.Namespace) -> int:
    from .preflight import run_doctor
    report = run_doctor(load_cfg(Path(args.config)), Path(args.out))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


def cmd_init(args: argparse.Namespace) -> int:
    cfg = load_cfg(Path(args.config))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    doctor = read_json(Path(args.doctor))
    if doctor.get("status") != "PASS":
        raise SystemExit("Doctor must PASS before initialization")
    if doctor.get("required_runtime_snapshot_sha256") != cfg.get("required_runtime_snapshot_sha256"):
        raise SystemExit("Doctor/config runtime snapshot mismatch")
    if (doctor.get("model_identity") or {}).get("configured_model_id") != cfg.get("model_id"):
        raise SystemExit("Doctor/config model_id mismatch")
    errors = verify_frozen(PACKAGE_ROOT / "frozen")
    if errors:
        raise SystemExit("Package frozen inputs failed: " + "; ".join(errors))
    target = out / "frozen"
    if target.exists():
        if verify_frozen(target):
            raise SystemExit("Existing experiment frozen inputs do not verify")
    else:
        shutil.copytree(PACKAGE_ROOT / "frozen", target)
    shutil.copy2(Path(args.doctor), out / "doctor.json")
    prompt_audit = {
        "schema_version": "ccrc.trajectory100.prompt_audit.v0.9.0",
        "stage_instructions": STAGE_INSTRUCTIONS,
        "stage_instruction_sha256": {k: sha256_text(v) for k, v in STAGE_INSTRUCTIONS.items()},
        "format_line": FORMAT_LINE,
        "format_retry": FORMAT_RETRY,
        "prior_answer_visible": False,
        "stateful_continuation": False,
        "same_option_order_within_item": True,
        "interpretation": "Cognitive-depth response curve under five interventions; not passive latent-state measurement.",
    }
    write_json(out / "prompt_audit.json", prompt_audit)
    manifest = {
        "schema_version": "ccrc.trajectory100.manifest.v0.9.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "harness_version": __version__,
        "experiment_id": cfg["experiment_id"],
        "development_pilot_not_confirmation": True,
        "protected_confirmatory_7818_used_for_selection_or_tuning": False,
        "config": cfg,
        "frozen_input_hash_manifest_sha256": sha256_file(target / "FROZEN_SHA256.txt"),
        "planned_items": 100,
        "planned_base_cells": 500,
        "format_retries_may_add_calls": True,
    }
    write_json(out / "manifest.json", manifest)
    if not (out / "runs.jsonl").exists():
        (out / "runs.jsonl").touch()
    refresh_hashes(out)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def cmd_transport(args: argparse.Namespace) -> int:
    from .preflight import run_transport_check
    cfg = load_cfg(Path(args.config)); out = Path(args.out)
    assert_config_frozen(cfg, read_json(out / "manifest.json"))
    report = run_transport_check(cfg, out / "transport_check.json")
    refresh_hashes(out)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


def _inputs(out: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return read_jsonl(out / "frozen" / "pilot_items.jsonl"), read_jsonl(out / "frozen" / "call_plan.jsonl")


def cmd_run(args: argparse.Namespace) -> int:
    from .runner import run_pilot
    cfg = load_cfg(Path(args.config)); out = Path(args.out)
    assert_config_frozen(cfg, read_json(out / "manifest.json"))
    if not (out / "transport_check.json").exists() or read_json(out / "transport_check.json").get("status") != "PASS":
        raise SystemExit("Transport check must PASS before experimental cells run")
    items, plan = _inputs(out)
    result = run_pilot(cfg, items, plan, out, limit=args.limit)
    refresh_hashes(out)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    report = validate_experiment(Path(args.out), full=args.full)
    refresh_hashes(Path(args.out))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


def cmd_analyze(args: argparse.Namespace) -> int:
    cfg = load_cfg(Path(args.config)); out = Path(args.out)
    assert_config_frozen(cfg, read_json(out / "manifest.json"))
    report = analyze(out, cfg["decision"])
    refresh_hashes(out)
    print(json.dumps(report["pilot_decision"], indent=2, sort_keys=True))
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    cfg = load_cfg(Path(args.config)); out = Path(args.out)
    assert_config_frozen(cfg, read_json(out / "manifest.json"))
    validation = validate_experiment(out, full=True)
    if validation["status"] != "PASS":
        raise SystemExit("Full validation failed; refusing to finalize")
    analysis = analyze(out, cfg["decision"])
    final = {
        "schema_version": "ccrc.trajectory100.finalized.v0.9.0",
        "finalized_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation_status": validation["status"],
        "planned_base_cells": 500,
        "completed_base_cells": validation["completed_cells"],
        "actual_model_calls": validation["actual_model_calls"],
        "pilot_disposition": analysis["pilot_decision"]["disposition"],
    }
    write_json(out / "FINALIZED.json", final)
    refresh_hashes(out)
    print(json.dumps(final, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ccrc-trajectory100")
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
