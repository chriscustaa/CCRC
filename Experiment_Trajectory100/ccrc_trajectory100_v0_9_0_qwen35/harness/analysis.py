from __future__ import annotations

import csv
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .design import STAGES
from .util import read_jsonl, write_json


def one_sided_exact_repairs_gt_harms(repairs: int, harms: int) -> float:
    n = repairs + harms
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(repairs, n + 1)) / (2**n)


def _stage_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for stage in STAGES:
        rows = [x["stages"][stage] for x in items]
        gaps = [float(x["confidence_gap"]) for x in rows]
        out[stage] = {
            "n": len(rows),
            "correct_n": sum(bool(x["correct"]) for x in rows),
            "accuracy": sum(bool(x["correct"]) for x in rows) / len(rows),
            "mean_confidence_gap": statistics.fmean(gaps),
            "median_confidence_gap": statistics.median(gaps),
        }
    return out


def _policy_metrics(items: list[dict[str, Any]]) -> dict[str, Any]:
    repairs = harms = switches = correct_n = 0
    for item in items:
        t0 = item["stages"]["T0"]
        late = [item["stages"][s] for s in ("T2", "T3", "T4")]
        late_answers = [x["parsed_answer"] for x in late]
        late_consensus = len(set(late_answers)) == 1
        late_answer = late_answers[0] if late_consensus else None
        positive_centered_confidence = statistics.median(
            item["control_centered_gap_change"][s] for s in ("T2", "T3", "T4")
        ) > 0
        switch = bool(late_consensus and late_answer != t0["parsed_answer"] and positive_centered_confidence)
        final = late_answer if switch else t0["parsed_answer"]
        truth = item["correct_answer"]
        switches += int(switch)
        repairs += int(not t0["correct"] and final == truth)
        harms += int(bool(t0["correct"]) and final != truth)
        correct_n += int(final == truth)
    return {
        "n": len(items),
        "switches": switches,
        "repairs": repairs,
        "harms": harms,
        "net": repairs - harms,
        "exact_one_sided_mcnemar_p": one_sided_exact_repairs_gt_harms(repairs, harms),
        "final_correct_n": correct_n,
        "final_accuracy": correct_n / len(items) if items else None,
        "rule": (
            "Switch from T0 only when T2=T3=T4 on a different answer and the median "
            "control-centered T2:T4 gap change is positive."
        ),
    }


def _trajectory_class(item: dict[str, Any]) -> str:
    answers = [item["stages"][s]["parsed_answer"] for s in STAGES]
    flips = sum(a != b for a, b in zip(answers, answers[1:]))
    t0_correct = bool(item["stages"]["T0"]["correct"])
    t4_correct = bool(item["stages"]["T4"]["correct"])
    if len(set(answers)) == 1:
        return "stable_correct" if t0_correct else "stable_wrong"
    if t0_correct and not t4_correct:
        return "correct_then_wrong_collapse"
    if not t0_correct and t4_correct:
        return "wrong_then_correct_recovery"
    if flips >= 2:
        return "oscillation"
    return "single_unresolved_flip"


def analyze(experiment_dir: Path, decision: dict[str, Any]) -> dict[str, Any]:
    runs = read_jsonl(experiment_dir / "runs.jsonl")
    if len(runs) != 500:
        raise RuntimeError(f"Full analysis requires 500 completed cells; observed {len(runs)}")
    items_frozen = read_jsonl(experiment_dir / "frozen" / "pilot_items.jsonl")
    frozen_by_id = {x["question_id"]: x for x in items_frozen}
    by_q: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in runs:
        by_q[row["question_id"]][row["stage"]] = row
    if any(set(rows) != set(STAGES) for rows in by_q.values()):
        raise RuntimeError("Every item must contain exactly T0..T4")

    controls = [qid for qid, item in frozen_by_id.items() if item["sample_stratum"] == "near_gap_control"]
    offsets = {"T0": 0.0}
    for stage in STAGES[1:]:
        deltas = [
            float(by_q[qid][stage]["confidence_gap"]) - float(by_q[qid]["T0"]["confidence_gap"])
            for qid in controls
        ]
        offsets[stage] = statistics.median(deltas)

    item_rows = []
    for qid in sorted(by_q):
        frozen = frozen_by_id[qid]
        stages = by_q[qid]
        gaps = {s: float(stages[s]["confidence_gap"]) for s in STAGES}
        adjusted = {s: (gaps[s] - gaps["T0"]) - offsets[s] for s in STAGES}
        answers = [stages[s]["parsed_answer"] for s in STAGES]
        row = {
            "question_id": qid,
            "source_bundle": frozen["source_bundle"],
            "sample_stratum": frozen["sample_stratum"],
            "subject": frozen.get("subject"),
            "correct_answer": frozen["correct_answer"],
            "prior_baseline_answer": frozen["prior_baseline_answer"],
            "prior_baseline_correct": frozen["prior_baseline_correct"],
            "prior_confidence_gap": frozen["prior_confidence_gap"],
            "stages": stages,
            "control_centered_gap_change": adjusted,
            "answer_flips": sum(a != b for a, b in zip(answers, answers[1:])),
            "unique_answers": len(set(answers)),
            "fresh_T0_matches_prior": stages["T0"]["parsed_answer"] == frozen["prior_baseline_answer"],
        }
        row["trajectory_class"] = _trajectory_class(row)
        item_rows.append(row)

    core = [x for x in item_rows if x["sample_stratum"] == "low_gap_core"]
    control_rows = [x for x in item_rows if x["sample_stratum"] == "near_gap_control"]
    core_policy = _policy_metrics(core)
    all_policy = _policy_metrics(item_rows)

    t0_wrong_core = [x for x in core if not x["stages"]["T0"]["correct"]]
    t0_correct_core = [x for x in core if x["stages"]["T0"]["correct"]]
    oracle_recoverable = sum(
        any(x["stages"][s]["correct"] for s in STAGES[1:]) for x in t0_wrong_core
    )
    collapse_any = sum(
        any(not x["stages"][s]["correct"] for s in STAGES[1:]) for x in t0_correct_core
    )

    minimum_repairs = int(decision["minimum_repairs"])
    minimum_net = int(decision["minimum_net"])
    max_ratio = float(decision["max_harm_repair_ratio"])
    ratio = core_policy["harms"] / core_policy["repairs"] if core_policy["repairs"] else math.inf
    if core_policy["repairs"] <= core_policy["harms"]:
        disposition = "KILL"
    elif (core_policy["repairs"] >= minimum_repairs and core_policy["net"] >= minimum_net
          and ratio <= max_ratio):
        disposition = "GO_TO_FRESH_300"
    else:
        disposition = "INCONCLUSIVE"

    summary = {
        "schema_version": "ccrc.trajectory100.analysis.v0.9.0",
        "experimental_base_cells": len(runs),
        "actual_model_calls": sum(int(x.get("model_call_count", 1)) for x in runs),
        "format_retry_calls": sum(int(x.get("model_call_count", 1)) - 1 for x in runs),
        "sample": {
            "items": len(item_rows),
            "low_gap_core": len(core),
            "near_gap_controls": len(control_rows),
            "fresh_T0_matches_prior_n": sum(x["fresh_T0_matches_prior"] for x in item_rows),
        },
        "control_stage_median_gap_offsets_from_T0": offsets,
        "stage_summary_all_100": _stage_summary(item_rows),
        "stage_summary_low_gap_core_60": _stage_summary(core),
        "trajectory_class_counts_all_100": dict(Counter(x["trajectory_class"] for x in item_rows)),
        "trajectory_class_counts_low_gap_core_60": dict(Counter(x["trajectory_class"] for x in core)),
        "answer_flip_counts_all_100": dict(Counter(str(x["answer_flips"]) for x in item_rows)),
        "diagnostics_low_gap_core": {
            "fresh_T0_wrong_n": len(t0_wrong_core),
            "fresh_T0_correct_n": len(t0_correct_core),
            "oracle_any_later_checkpoint_recovers_n": oracle_recoverable,
            "oracle_any_later_checkpoint_recovers_rate_among_T0_wrong": (
                oracle_recoverable / len(t0_wrong_core) if t0_wrong_core else None
            ),
            "any_later_checkpoint_wrong_n_among_T0_correct": collapse_any,
            "oracle_warning": "Uses truth and is diagnostic only; it is not a deployable policy.",
        },
        "frozen_trajectory_policy": {
            "low_gap_core_primary": core_policy,
            "all_100_secondary": all_policy,
        },
        "pilot_decision": {
            "disposition": disposition,
            "thresholds": decision,
            "observed_harm_repair_ratio": ratio if math.isfinite(ratio) else None,
            "meaning": {
                "GO_TO_FRESH_300": "Freeze the promising rule and test it on 300 fresh development items.",
                "INCONCLUSIVE": "Do not tune on these 100; redesign only with a new preregistered pilot.",
                "KILL": "Retire this five-stage trajectory policy.",
            }[disposition],
        },
        "interpretation_limits": [
            "This is a reused, outcome-enriched development sample, not an efficacy confirmation.",
            "The five points are responses to distinct prompt interventions, not passive reads of a latent internal state.",
            "Raw gaps are not assumed comparable across templates; the policy uses control-centered changes.",
            "No result estimates the user's proposed 25% irreducible-question prevalence.",
        ],
    }
    write_json(experiment_dir / "analysis.json", summary)

    with (experiment_dir / "trajectory_items.csv").open("w", encoding="utf-8", newline="") as f:
        fields = [
            "question_id", "source_bundle", "sample_stratum", "subject", "correct_answer",
            "prior_baseline_correct", "prior_confidence_gap", "fresh_T0_matches_prior",
            "answer_flips", "unique_answers", "trajectory_class",
        ] + [f"{s}_answer" for s in STAGES] + [f"{s}_gap" for s in STAGES] + [f"{s}_centered_delta" for s in STAGES]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for item in item_rows:
            flat = {k: item[k] for k in fields if k in item}
            for s in STAGES:
                flat[f"{s}_answer"] = item["stages"][s]["parsed_answer"]
                flat[f"{s}_gap"] = item["stages"][s]["confidence_gap"]
                flat[f"{s}_centered_delta"] = item["control_centered_gap_change"][s]
            writer.writerow(flat)
    return summary
