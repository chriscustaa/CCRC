#!/usr/bin/env python3
"""Build the frozen 100-item trajectory pilot from audited pre-confirmatory data."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from harness.design import build_call_plan, stage_messages, validate_call_plan  # noqa: E402
from harness.util import canonical_json, sha256_file, sha256_text, write_json, write_jsonl  # noqa: E402

SEED = 2026082809
I5_ZIP_SHA256 = "b2489e4972dae7925b83a3f7d580e69221199e34d530a24220550c49a6d322ad"
CONSENSUS_ZIP_SHA256 = "b4a8ba047c4d80060020834e54bec06f244fc00c556ce15b05af7221b60e2afd"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def verify_internal_hashes(root: Path) -> list[dict[str, str]]:
    verified = []
    for line in (root / "hashes.sha256").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, name = line.split(maxsplit=1)
        name = name.strip().lstrip("*")
        path = root / name
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(f"Internal source hash failed for {path}")
        verified.append({"file": name, "sha256": observed})
    return verified


def choices_list(item: dict[str, Any]) -> list[str]:
    raw = item.get("choices", item.get("options"))
    if isinstance(raw, dict):
        return [str(raw[x]) for x in "ABCD"]
    return [str(x) for x in raw]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--i5-dir", type=Path, required=True)
    parser.add_argument("--i5-zip", type=Path, required=True)
    parser.add_argument("--consensus-dir", type=Path, required=True)
    parser.add_argument("--consensus-zip", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if sha256_file(args.i5_zip) != I5_ZIP_SHA256:
        raise RuntimeError("I5 ZIP does not match the audited source")
    if sha256_file(args.consensus_zip) != CONSENSUS_ZIP_SHA256:
        raise RuntimeError("Consensus600 ZIP does not match the audited source")
    source_internal = {
        "experiment_i5gated1000": verify_internal_hashes(args.i5_dir),
        "experiment_consensus600": verify_internal_hashes(args.consensus_dir),
    }

    i5_items = read_jsonl(args.i5_dir / "items.jsonl")
    i5_runs = [x for x in read_jsonl(args.i5_dir / "runs.jsonl") if x.get("condition") == "B0"]
    c_items = read_jsonl(args.consensus_dir / "items.jsonl")
    c_runs = [x for x in read_jsonl(args.consensus_dir / "runs.jsonl") if x.get("branch") == "B1"]
    if (len(i5_items), len(i5_runs), len(c_items), len(c_runs)) != (1000, 1000, 600, 600):
        raise RuntimeError("Unexpected source cardinality")

    i5_by_id = {x["question_id"]: x for x in i5_items}
    c_by_id = {x["task_id"]: x for x in c_items}
    consensus_stems = {x["stem_sha256"] for x in c_items}
    overlap = {x["question_id"] for x in i5_items if x["semantic_stem_sha256"] in consensus_stems}
    if len(overlap) != 58:
        raise RuntimeError(f"Expected 58 I5/consensus overlaps, observed {len(overlap)}")

    pool: list[dict[str, Any]] = []
    for run in c_runs:
        raw = c_by_id[run["task_id"]]
        item = {
            "question_id": f"c600:{run['task_id']}",
            "source_bundle": "experiment_consensus600",
            "source_item_id": run["task_id"],
            "source_id": raw.get("source_id"),
            "subject": raw.get("domain"),
            "question": raw["question"],
            "choices": choices_list(raw),
            "correct_answer": raw["correct"],
            "canonical_stem_sha256": raw["stem_sha256"],
            "prior_baseline_answer": run["parsed_first"],
            "prior_baseline_correct": bool(run["correct_first"]),
            "prior_confidence_gap": float(run["decision_gap"]),
            "prior_prompt_sha256": run["prompt_sha256"],
        }
        if run.get("messages") != stage_messages(item, "T0"):
            raise RuntimeError(f"Could not reconstruct consensus T0 prompt: {item['question_id']}")
        pool.append(item)

    for run in i5_runs:
        raw = i5_by_id[run["question_id"]]
        if raw["question_id"] in overlap:
            continue
        item = {
            "question_id": f"i5:{run['question_id']}",
            "source_bundle": "experiment_i5gated1000_fresh_only",
            "source_item_id": run["question_id"],
            "source_id": raw.get("source_id"),
            "subject": raw.get("subject"),
            "question": raw["question"],
            "choices": choices_list(raw),
            "correct_answer": raw["correct_answer"],
            "canonical_stem_sha256": raw["semantic_stem_sha256"],
            "prior_baseline_answer": run["parsed_answer"],
            "prior_baseline_correct": run["parsed_answer"] == run["correct_answer"],
            "prior_confidence_gap": float(run["sensor_gap"]),
            "prior_prompt_sha256": run["prompt_sha256"],
        }
        if run.get("messages") != stage_messages(item, "T0"):
            raise RuntimeError(f"Could not reconstruct I5 T0 prompt: {item['question_id']}")
        pool.append(item)

    if len(pool) != 1542 or len({x["canonical_stem_sha256"] for x in pool}) != 1542:
        raise RuntimeError("Deduplicated development pool changed")

    core = sorted(
        (x for x in pool if x["prior_confidence_gap"] < 0.20),
        key=lambda x: (x["canonical_stem_sha256"], x["question_id"]),
    )
    if (len(core), sum(not x["prior_baseline_correct"] for x in core)) != (60, 43):
        raise RuntimeError("Low-gap core changed")
    for item in core:
        item["sample_stratum"] = "low_gap_core"

    eligible = [x for x in pool if x["prior_confidence_gap"] >= 0.20]
    correct_controls = sorted(
        (x for x in eligible if x["prior_baseline_correct"]),
        key=lambda x: (x["prior_confidence_gap"], x["canonical_stem_sha256"]),
    )[:33]
    wrong_controls = sorted(
        (x for x in eligible if not x["prior_baseline_correct"]),
        key=lambda x: (x["prior_confidence_gap"], x["canonical_stem_sha256"]),
    )[:7]
    controls = correct_controls + wrong_controls
    for item in controls:
        item["sample_stratum"] = "near_gap_control"

    selected = sorted(core + controls, key=lambda x: x["question_id"])
    if len(selected) != 100 or len({x["question_id"] for x in selected}) != 100:
        raise RuntimeError("Pilot selection is not 100 unique items")
    if Counter(x["prior_baseline_correct"] for x in selected) != Counter({True: 50, False: 50}):
        raise RuntimeError("Pilot construction labels are not balanced 50/50")

    plan = build_call_plan(selected, SEED)
    errors = validate_call_plan(selected, plan)
    if errors:
        raise RuntimeError("Invalid call plan: " + "; ".join(errors))

    args.out.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.out / "pilot_items.jsonl", selected)
    write_jsonl(args.out / "call_plan.jsonl", plan)
    provenance = {
        "schema_version": "ccrc.trajectory100.provenance.v0.9.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "frozen_seed": SEED,
        "source_zip_sha256": {
            "experiment_i5gated1000.zip": I5_ZIP_SHA256,
            "experiment_consensus600.zip": CONSENSUS_ZIP_SHA256,
        },
        "source_internal_hashes_verified": source_internal,
        "protected_confirmatory_7818_used_for_selection_or_tuning": False,
        "counts": {
            "deduplicated_preconfirmatory_pool": len(pool),
            "i5_consensus_overlap_excluded": len(overlap),
            "pilot_items": len(selected),
            "planned_cells": len(plan),
            "low_gap_core": len(core),
            "low_gap_core_prior_wrong": sum(not x["prior_baseline_correct"] for x in core),
            "low_gap_core_prior_correct": sum(x["prior_baseline_correct"] for x in core),
            "near_gap_controls": len(controls),
            "construction_prior_wrong": sum(not x["prior_baseline_correct"] for x in selected),
            "construction_prior_correct": sum(x["prior_baseline_correct"] for x in selected),
        },
        "selection": {
            "core": "All unique pre-confirmatory items with prior T0 gap < 0.20.",
            "controls": (
                "Among remaining items, the 33 prior-correct and 7 prior-wrong smallest-gap rows, "
                "tie-broken by canonical stem hash, to balance construction labels 50/50."
            ),
            "no_replacement_after_fresh_T0": True,
        },
        "control_gap_ranges": {
            "prior_correct_min": min(x["prior_confidence_gap"] for x in correct_controls),
            "prior_correct_max": max(x["prior_confidence_gap"] for x in correct_controls),
            "prior_wrong_min": min(x["prior_confidence_gap"] for x in wrong_controls),
            "prior_wrong_max": max(x["prior_confidence_gap"] for x in wrong_controls),
        },
        "design": {
            "stages_per_item": 5,
            "stateless": True,
            "prior_answer_visible": False,
            "same_option_order_at_all_stages": True,
            "call_order_randomized_after_plan_creation": True,
            "format_retries_are_extra_calls_not_extra_cells": True,
        },
    }
    write_json(args.out / "provenance.json", provenance)
    lines = []
    for path in sorted(args.out.iterdir()):
        if path.is_file() and path.name != "FROZEN_SHA256.txt":
            lines.append(f"{sha256_file(path)}  {path.name}")
    (args.out / "FROZEN_SHA256.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
