from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .runner import benchmark_output, benchmark_parsed
from .util import canonical_json, read_json, read_jsonl, sha256_text


def validate_experiment(experiment_dir: Path) -> dict[str, Any]:
    items = read_jsonl(experiment_dir / "items.jsonl")
    runs = read_jsonl(experiment_dir / "runs.jsonl")
    manifest = read_json(experiment_dir / "manifest.json")
    errors: list[str] = []
    warnings: list[str] = []

    item_by_id = {x["source_id"]: x for x in items}
    if len(item_by_id) != len(items):
        errors.append("Duplicate source_id in items.jsonl")

    keys = [r.get("run_key") for r in runs]
    dupes = [k for k, c in Counter(keys).items() if c > 1]
    if dupes:
        errors.append(f"Duplicate run_key(s): {dupes[:10]}")

    run_by_key = {r["run_key"]: r for r in runs}

    transports = {r.get("transport") for r in runs}
    if len(transports) > 1:
        errors.append(f"Mixed transports in runs.jsonl: {sorted(transports)}")

    frozen_model = (manifest.get("planned_model") or {}).get("model_id")
    frozen_snapshot = (manifest.get("planned_model") or {}).get("observed_snapshot_sha256")
    for r in runs:
        if r.get("model_id") != frozen_model:
            errors.append(
                f"Run model_id differs from frozen manifest: {r.get('run_key')}"
            )
        if r.get("model_snapshot_sha256") != frozen_snapshot:
            errors.append(
                f"Run model snapshot differs from frozen manifest: {r.get('run_key')}"
            )

    for r in runs:
        qid = r["question_id"]
        if qid not in item_by_id:
            errors.append(f"Run references unknown question_id: {qid}")
        expected_hash = sha256_text(canonical_json(r["messages"]))
        if r.get("prompt_sha256") != expected_hash:
            errors.append(f"Prompt hash mismatch: {r['run_key']}")
        if "raw_output" not in r:
            errors.append(f"Missing raw_output: {r['run_key']}")
        if r["condition"] != "baseline":
            bk = r.get("lineage_baseline_key")
            if not bk or bk not in run_by_key:
                errors.append(f"Missing baseline lineage: {r['run_key']}")
            else:
                expected_assistant = benchmark_output(run_by_key[bk])
                assistant_msgs = [
                    m.get("content")
                    for m in r.get("messages", [])
                    if m.get("role") == "assistant"
                ]
                if not assistant_msgs or assistant_msgs[0] != expected_assistant:
                    errors.append(
                        f"Follow-up lineage does not carry SycoBench benchmark baseline output: {r['run_key']}"
                    )
        if r.get("parsed_first") is None and not r.get("format_retry"):
            warnings.append(f"Unparsed first response without retry: {r['run_key']}")

    # Infer variants actually present and check native completeness.
    variants_by_q = defaultdict(set)
    for r in runs:
        variants_by_q[r["question_id"]].add(int(r["variant_id"]))

    for qid, vids in variants_by_q.items():
        item = item_by_id[qid]
        for vid in sorted(vids):
            base_key = f"{qid}|v{vid}|baseline"
            if base_key not in run_by_key:
                errors.append(f"Missing baseline: {base_key}")
                continue
            for ptype in ("doubt", "authority", "wrong_suggest"):
                k = f"{qid}|v{vid}|{ptype}"
                if k not in run_by_key:
                    errors.append(f"Missing pressure condition: {k}")

            b = run_by_key[base_key]
            bp = benchmark_parsed(b)
            ck = f"{qid}|v{vid}|correct_suggest"
            if bp is not None and bp != item["correct"] and ck not in run_by_key:
                errors.append(f"Missing correct_suggest for baseline-wrong case: {ck}")
            if bp == item["correct"] and ck in run_by_key:
                warnings.append(f"correct_suggest present though baseline was correct: {ck}")

    return {
        "ok": not errors,
        "n_items": len(items),
        "n_runs": len(runs),
        "errors": errors,
        "warnings": warnings,
    }
