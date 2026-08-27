#!/usr/bin/env python3
"""Build the frozen 568-cell replay inputs from audited experiment bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from harness.design import build_call_plan, validate_call_plan  # noqa: E402
from harness.util import canonical_json, sha256_file, sha256_text, write_json, write_jsonl  # noqa: E402

LETTERS = "ABCD"
FROZEN_SEED = 2026082607
I5_ZIP_SHA256 = "b2489e4972dae7925b83a3f7d580e69221199e34d530a24220550c49a6d322ad"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def norm_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value)).casefold()
    return re.sub(r"\s+", " ", value).strip()


def choices_list(item: dict[str, Any]) -> list[str]:
    raw = item.get("choices", item.get("options"))
    if isinstance(raw, dict):
        return [str(raw[x]) for x in LETTERS]
    return [str(x) for x in raw]


def correct_letter(item: dict[str, Any]) -> str:
    return str(item.get("correct_answer", item.get("correct")))


def fingerprint(item: dict[str, Any]) -> str:
    payload = {
        "question": norm_text(item["question"]),
        "choices": [norm_text(x) for x in choices_list(item)],
        "correct": correct_letter(item),
    }
    return sha256_text(canonical_json(payload))


def verify_hashes(root: Path) -> list[dict[str, str]]:
    hash_path = root / "hashes.sha256"
    verified = []
    for line in hash_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, name = line.split(maxsplit=1)
        name = name.strip().lstrip("*")
        path = root / name
        observed = sha256_file(path)
        if observed != expected:
            raise RuntimeError(f"Internal source hash failed for {path}: {observed} != {expected}")
        verified.append({"file": name, "sha256": observed})
    return verified


def majority3(values: list[str]) -> str | None:
    value, n = Counter(values).most_common(1)[0]
    return value if n >= 2 else None


def replay_original_controller(items: list[dict[str, Any]], by_q: dict[str, dict[str, Any]]) -> dict[str, int]:
    metrics = Counter()
    for item in items:
        qid = item["question_id"]
        rows = by_q[qid]
        truth = item["correct_answer"]
        baseline = rows["B0"]["parsed_answer"]
        if float(rows["B0"]["sensor_gap"]) >= 0.20:
            final = baseline
        else:
            metrics["routed"] += 1
            d0 = rows["D0"]["parsed_answer"]
            if baseline == d0:
                final = baseline
            else:
                metrics["escalated"] += 1
                final = majority3([d0, rows["V1"]["parsed_answer"], rows["V2"]["parsed_answer"]])
        metrics["repairs"] += int(baseline != truth and final == truth)
        metrics["harms"] += int(baseline == truth and final != truth)
        metrics["strict_correct"] += int(final == truth)
    metrics["net"] = metrics["repairs"] - metrics["harms"]
    return dict(metrics)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--i5-dir", type=Path, required=True)
    parser.add_argument("--i5-zip", type=Path, required=True)
    parser.add_argument("--prior-root", type=Path, required=True)
    parser.add_argument("--prior-zip-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if sha256_file(args.i5_zip) != I5_ZIP_SHA256:
        raise RuntimeError("Uploaded I5-1000 ZIP hash does not match the audited bundle")
    internal_hashes = verify_hashes(args.i5_dir)
    items_raw = read_jsonl(args.i5_dir / "items.jsonl")
    runs = read_jsonl(args.i5_dir / "runs.jsonl")
    if len(items_raw) != 1000 or len(runs) != 4142:
        raise RuntimeError(f"Unexpected I5 cardinality: items={len(items_raw)} runs={len(runs)}")

    by_q: dict[str, dict[str, Any]] = defaultdict(dict)
    for row in runs:
        by_q[row["question_id"]][row["condition"]] = row

    prior_dirs = sorted(p.parent for p in args.prior_root.glob("*/*/items.jsonl"))
    if len(prior_dirs) != 4:
        raise RuntimeError(f"Expected four prior bundles, found {len(prior_dirs)}")
    prior_items_by_bundle: dict[str, list[dict[str, Any]]] = {}
    prior_source_hashes = {}
    for root in prior_dirs:
        name = root.name
        prior_items_by_bundle[name] = read_jsonl(root / "items.jsonl")
        verify_hashes(root)
        zip_path = args.prior_zip_root / f"{name}.zip"
        prior_source_hashes[name] = sha256_file(zip_path)

    consensus_fps = {fingerprint(x) for x in prior_items_by_bundle["experiment_consensus600"]}
    overlap_ids = {x["question_id"] for x in items_raw if fingerprint(x) in consensus_fps}
    if len(overlap_ids) != 58:
        raise RuntimeError(f"Consensus overlap changed: expected 58, observed {len(overlap_ids)}")

    normalized_items = []
    policy_rows = []
    replay_items = []
    verifier_union = {q for q, rows in by_q.items() if "V1" in rows or "V2" in rows}
    if len(verifier_union) != 71:
        raise RuntimeError(f"Verifier union changed: expected 71, observed {len(verifier_union)}")

    for raw in items_raw:
        qid = raw["question_id"]
        rows = by_q[qid]
        item = {
            "question_id": qid,
            "source_id": raw["source_id"],
            "source_index": raw.get("source_index"),
            "subject": raw.get("subject"),
            "question": raw["question"],
            "choices": choices_list(raw),
            "correct_answer": raw["correct_answer"],
            "semantic_stem_sha256": raw.get("semantic_stem_sha256"),
            "canonical_fingerprint_sha256": fingerprint(raw),
            "overlap_consensus600": qid in overlap_ids,
        }
        normalized_items.append(item)
        b0, d0 = rows["B0"], rows["D0"]
        b5, d5 = rows["B5"], rows["D5"]
        policy_rows.append({
            "question_id": qid,
            "source_id": item["source_id"],
            "correct_answer": item["correct_answer"],
            "overlap_consensus600": item["overlap_consensus600"],
            "primary_deduplicated_cohort": not item["overlap_consensus600"],
            "B0": {"answer": b0["parsed_answer"], "sensor_gap": b0["sensor_gap"], "prompt_sha256": b0["prompt_sha256"]},
            "D0": {"answer": d0["parsed_answer"], "prompt_sha256": d0["prompt_sha256"]},
            "B5_archived": {"answer": b5["parsed_answer"], "sensor_gap": b5["sensor_gap"], "prompt_sha256": b5["prompt_sha256"]},
            "D5_archived": {"answer": d5["parsed_answer"], "prompt_sha256": d5["prompt_sha256"]},
            "theta_020_gate": float(b0["sensor_gap"]) < 0.20,
            "theta_020_verifier_escalation": float(b0["sensor_gap"]) < 0.20 and b0["parsed_answer"] != d0["parsed_answer"],
            "theta_050_gate": float(b0["sensor_gap"]) < 0.50,
        })
        if qid in verifier_union:
            replay_item = dict(item)
            replay_item["original_verifiers"] = {
                stream: {
                    "answer": rows[stream]["parsed_answer"],
                    "display_answer": rows[stream]["parsed_display_answer"],
                    "option_order": rows[stream]["option_order"],
                    "prompt_sha256": rows[stream]["prompt_sha256"],
                }
                for stream in ("V1", "V2")
            }
            replay_items.append(replay_item)

    replay_items.sort(key=lambda x: x["question_id"])
    policy_rows.sort(key=lambda x: x["question_id"])
    normalized_items.sort(key=lambda x: x["question_id"])

    original = replay_original_controller(normalized_items, by_q)
    expected_original = {"routed": 35, "escalated": 20, "repairs": 6, "harms": 3, "strict_correct": 784, "net": 3}
    if original != expected_original:
        raise RuntimeError(f"Original controller replay changed: {original} != {expected_original}")

    plan = build_call_plan(replay_items, FROZEN_SEED)
    plan_errors = validate_call_plan(replay_items, plan)
    if plan_errors:
        raise RuntimeError("Invalid frozen call plan: " + "; ".join(plan_errors))

    evidence: dict[str, dict[str, Any]] = {}
    for bundle, bundle_items in prior_items_by_bundle.items():
        for item in bundle_items:
            fp = fingerprint(item)
            row = evidence.setdefault(fp, {"canonical_fingerprint_sha256": fp, "sources": []})
            row["sources"].append({"bundle": bundle, "source_id": item.get("source_id")})
    for item in normalized_items:
        fp = item["canonical_fingerprint_sha256"]
        row = evidence.setdefault(fp, {"canonical_fingerprint_sha256": fp, "sources": []})
        row["sources"].append({"bundle": "experiment_i5gated1000", "source_id": item["source_id"]})
    if len(evidence) != 1812:
        raise RuntimeError(f"Evidence stem union changed: expected 1812, observed {len(evidence)}")

    args.out.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.out / "all_items.jsonl", normalized_items)
    write_jsonl(args.out / "policy_backbone.jsonl", policy_rows)
    write_jsonl(args.out / "replay_items.jsonl", replay_items)
    write_jsonl(args.out / "call_plan.jsonl", plan)
    write_jsonl(args.out / "all_evidence_stems.jsonl", [evidence[k] for k in sorted(evidence)])
    provenance = {
        "schema_version": "ccrc.position_replay.provenance.v0.7.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "frozen_seed": FROZEN_SEED,
        "source_bundle_sha256": {
            "experiment_i5gated1000.zip": I5_ZIP_SHA256,
            **prior_source_hashes,
        },
        "i5_internal_hashes_verified": internal_hashes,
        "counts": {
            "all_items": len(normalized_items),
            "deduplicated_primary_items": sum(not x["overlap_consensus600"] for x in normalized_items),
            "consensus600_overlaps": len(overlap_ids),
            "replay_items": len(replay_items),
            "planned_cells": len(plan),
            "theta_020_gate": sum(x["theta_020_gate"] for x in policy_rows),
            "theta_020_verifier_escalation": sum(x["theta_020_verifier_escalation"] for x in policy_rows),
            "all_evidence_unique_stems": len(evidence),
        },
        "original_theta_020_controller": original,
        "design": {
            "placements_per_item": 4,
            "replicate_streams": ["R1", "R2"],
            "base_cells": len(plan),
            "format_retries_are_extra_calls_not_extra_cells": True,
            "controller_replay_uses_one_R1_and_one_R2_cell_per_item": True,
            "eight_cell_majority_forbidden": True,
        },
    }
    write_json(args.out / "provenance.json", provenance)

    hash_lines = []
    for path in sorted(args.out.iterdir()):
        if path.is_file() and path.name != "FROZEN_SHA256.txt":
            hash_lines.append(f"{sha256_file(path)}  {path.name}")
    (args.out / "FROZEN_SHA256.txt").write_text("\n".join(hash_lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(provenance, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
