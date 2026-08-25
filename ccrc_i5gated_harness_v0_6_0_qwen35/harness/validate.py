from __future__ import annotations

from typing import Any


def validate(items: list[dict[str, Any]], runs: list[dict[str, Any]], cfg: dict[str, Any], *, require_full: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    by_key = {}
    for row in runs:
        key = row.get("run_key")
        if key in by_key:
            errors.append(f"duplicate run_key: {key}")
        by_key[key] = row

    thresholds = [float(x) for x in (cfg.get("controller") or {}).get("thresholds", [0.20, 0.50])]
    max_theta = max(thresholds)
    for item in items:
        qid = item["question_id"]
        for condition in ("B0", "B5", "D0", "D5"):
            row = by_key.get(f"{qid}:{condition}")
            if require_full and not row:
                errors.append(f"missing {qid}:{condition}")
                continue
            if not row:
                continue
            expected_i5 = condition in {"B5", "D5"}
            if bool(row.get("i5_enabled")) != expected_i5:
                errors.append(f"I5 contamination flag mismatch: {qid}:{condition}")
            if condition.startswith("D") and row.get("prior_answer_visible"):
                errors.append(f"blind branch exposes prior answer: {qid}:{condition}")
            if bool(cfg.get("require_reasoning_off", True)) and row.get("reasoning_detected"):
                errors.append(f"reasoning detected: {qid}:{condition}")

        b0, b5, d0, d5 = (by_key.get(f"{qid}:{c}") for c in ("B0", "B5", "D0", "D5"))
        needs_v = False
        for b, d in ((b0, d0), (b5, d5)):
            if not b or not d:
                continue
            gap = b.get("sensor_gap")
            if gap is None:
                warnings.append(f"sensor missing; fail-closed route: {qid}:{b['condition']}")
            if (gap is None or float(gap) < max_theta) and isinstance(b.get("parsed_answer"), str) and b.get("parsed_answer") in "ABCD" and isinstance(d.get("parsed_answer"), str) and d.get("parsed_answer") in "ABCD" and b.get("parsed_answer") != d.get("parsed_answer"):
                needs_v = True
        if require_full and needs_v:
            for v in ("V1", "V2"):
                row = by_key.get(f"{qid}:{v}")
                if not row:
                    errors.append(f"missing required verifier {qid}:{v}")
                elif row.get("i5_enabled") or row.get("prior_answer_visible"):
                    errors.append(f"verifier contamination: {qid}:{v}")

        v1, v2 = by_key.get(f"{qid}:V1"), by_key.get(f"{qid}:V2")
        if v1 and v2 and v1.get("option_order") == v2.get("option_order"):
            errors.append(f"verifier permutations identical: {qid}")

    snapshots = {r.get("model_snapshot_sha256") for r in runs if r.get("model_snapshot_sha256")}
    if len(snapshots) > 1:
        errors.append(f"multiple runtime snapshots in runs: {sorted(snapshots)}")
    required = ((cfg.get("runtime") or {}).get("required_snapshot_sha256"))
    if required and snapshots and snapshots != {required}:
        errors.append(f"runtime snapshot mismatch: required={required}, observed={sorted(snapshots)}")

    return {
        "schema_version": "ccrc.i5gated.validation.v0.6.0",
        "status": "PASS" if not errors else "BLOCK",
        "errors": errors,
        "warnings": warnings,
        "item_n": len(items),
        "run_n": len(runs),
        "runtime_snapshots": sorted(snapshots),
    }
