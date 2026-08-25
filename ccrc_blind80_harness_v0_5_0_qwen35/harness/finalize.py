from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .util import sha256_file, write_json
from .validate import validate_experiment

IMMUTABLE_TARGETS = [
    "doctor.json",
    "transport_check.json",
    "manifest.json",
    "upstream_questions.json",
    "excluded_items.jsonl",
    "items.jsonl",
    "prompt_audit.json",
    "runs.jsonl",
    "summary.csv",
    "summary.json",
    "transition_candidates.jsonl",
]


def finalize_experiment(experiment_dir: Path) -> dict[str, Any]:
    final_path = experiment_dir / "FINALIZED.json"
    if final_path.exists():
        raise RuntimeError("Experiment is already finalized")

    validation = validate_experiment(experiment_dir, require_full=True)
    if not validation["ok"]:
        raise RuntimeError(f"Finalization blocked: {validation['errors'][:5]}")

    files = {}
    for name in IMMUTABLE_TARGETS:
        p = experiment_dir / name
        if not p.exists():
            raise RuntimeError(f"Finalization blocked: missing {name}")
        files[name] = {"size_bytes": p.stat().st_size, "sha256": sha256_file(p)}

    out = {
        "schema_version": "ccrc.blind80.finalized.v0.5.0",
        "finalized_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation": validation,
        "files": files,
    }
    write_json(final_path, out)

    ledger_names = IMMUTABLE_TARGETS + ["FINALIZED.json"]
    ledger = {name: sha256_file(experiment_dir / name) for name in ledger_names}
    (experiment_dir / "hashes.sha256").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in ledger.items()),
        encoding="utf-8",
        newline="\n",
    )

    for name, meta in files.items():
        p = experiment_dir / name
        if p.stat().st_size != meta["size_bytes"] or sha256_file(p) != meta["sha256"]:
            raise RuntimeError(f"Post-write rehash failed: {name}")
    if sha256_file(final_path) != ledger["FINALIZED.json"]:
        raise RuntimeError("FINALIZED.json rehash failed")
    return out
