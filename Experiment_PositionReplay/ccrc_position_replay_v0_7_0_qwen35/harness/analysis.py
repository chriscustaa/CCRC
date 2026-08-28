from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any

from .design import LETTERS
from .util import read_jsonl, write_json


def majority3(values: list[str]) -> str | None:
    value, n = Counter(values).most_common(1)[0]
    return value if n >= 2 else None


def exact_sign_test_two_sided(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2**n)
    return min(1.0, 2 * tail)


def _slot_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for label, subset in [("pooled", rows)] + [
        (stream, [x for x in rows if x["replicate_stream"] == stream])
        for stream in ("R1", "R2")
    ]:
        by_slot = {}
        for slot in LETTERS:
            slot_rows = [x for x in subset if x["correct_display_slot"] == slot]
            correct_n = sum(bool(x["correct"]) for x in slot_rows)
            by_slot[slot] = {
                "n": len(slot_rows),
                "correct_n": correct_n,
                "accuracy": correct_n / len(slot_rows) if slot_rows else None,
            }
        chosen = Counter(x["parsed_display_answer"] for x in subset)
        out[label] = {
            "n": len(subset),
            "accuracy_by_correct_display_slot": by_slot,
            "chosen_display_counts": {slot: chosen[slot] for slot in LETTERS},
        }
    return out


def _within_item_slot_contrasts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_q_slot: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        by_q_slot[row["question_id"]][row["correct_display_slot"]].append(int(bool(row["correct"])))
    contrasts = []
    for i, left in enumerate(LETTERS):
        for right in LETTERS[i + 1 :]:
            diffs = []
            for slots in by_q_slot.values():
                if len(slots[left]) == 2 and len(slots[right]) == 2:
                    diffs.append(sum(slots[left]) / 2 - sum(slots[right]) / 2)
            wins = sum(x > 0 for x in diffs)
            losses = sum(x < 0 for x in diffs)
            contrasts.append({
                "left": left,
                "right": right,
                "n_items": len(diffs),
                "mean_accuracy_difference_left_minus_right": sum(diffs) / len(diffs) if diffs else None,
                "items_left_better": wins,
                "items_right_better": losses,
                "items_tied": len(diffs) - wins - losses,
                "two_sided_exact_sign_p": exact_sign_test_two_sided(wins, losses),
            })
    return contrasts


def _representation_instability(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_q: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_q_placement: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_q[row["question_id"]].append(row)
        by_q_placement[(row["question_id"], row["placement"])][row["replicate_stream"]] = row
    canonical_counts = [len({r["parsed_answer"] for r in rs}) for rs in by_q.values()]
    replicate_pairs = [x for x in by_q_placement.values() if set(x) == {"R1", "R2"}]
    replicate_agree = sum(x["R1"]["parsed_answer"] == x["R2"]["parsed_answer"] for x in replicate_pairs)
    return {
        "items": len(by_q),
        "items_with_more_than_one_canonical_answer_across_eight_cells": sum(x > 1 for x in canonical_counts),
        "items_with_three_or_more_canonical_answers_across_eight_cells": sum(x >= 3 for x in canonical_counts),
        "same_placement_replicate_pairs": len(replicate_pairs),
        "same_placement_replicate_agreement_n": replicate_agree,
        "same_placement_replicate_agreement_rate": replicate_agree / len(replicate_pairs) if replicate_pairs else None,
        "interpretation": (
            "R1/R2 share wording and placement but use frozen distinct seed streams. "
            "Disagreement measures replicate/seed/runtime instability, not a wording effect."
        ),
    }


def _balanced_schedule_distribution(
    item_pairs: list[list[tuple[int, int, int]]],
) -> dict[str, Any]:
    """Exactly count all schedules balanced within one item across four slots.

    Every item contributes one ordered (R1 slot, R2 slot) pair. Identical slots
    across streams are admissible, matching independent uniform slot assignment.
    A valid schedule has per-stream slot counts differing by at most one.
    """
    n = len(item_pairs)
    if n == 0:
        return {
            "schedule_count": 1,
            "net_distribution": {"0": 1},
            "positive_schedule_count": 0,
            "positive_schedule_fraction": 0.0,
            "exact_expected_net": 0.0,
        }
    floor_n, remainder = divmod(n, 4)
    ceil_n = floor_n + int(remainder > 0)
    # State: counts for A/B/C in R1, counts for A/B/C in R2, accumulated net.
    states: Counter[tuple[int, int, int, int, int, int, int]] = Counter({(0, 0, 0, 0, 0, 0, 0): 1})
    for item_i, pairs in enumerate(item_pairs, 1):
        nxt: Counter[tuple[int, int, int, int, int, int, int]] = Counter()
        for state, multiplicity in states.items():
            a1, b1, c1, a2, b2, c2, net = state
            for slot1, slot2, delta in pairs:
                cts1 = [a1, b1, c1]
                cts2 = [a2, b2, c2]
                if slot1 < 3:
                    cts1[slot1] += 1
                if slot2 < 3:
                    cts2[slot2] += 1
                d1 = item_i - sum(cts1)
                d2 = item_i - sum(cts2)
                if max(*cts1, d1, *cts2, d2) > ceil_n:
                    continue
                nxt[(*cts1, *cts2, net + delta)] += multiplicity
        states = nxt

    distribution: Counter[int] = Counter()
    for state, multiplicity in states.items():
        a1, b1, c1, a2, b2, c2, net = state
        counts1 = (a1, b1, c1, n - a1 - b1 - c1)
        counts2 = (a2, b2, c2, n - a2 - b2 - c2)
        valid1 = all(x in {floor_n, ceil_n} for x in counts1)
        valid2 = all(x in {floor_n, ceil_n} for x in counts2)
        if valid1 and valid2:
            distribution[net] += multiplicity
    total = sum(distribution.values())
    if total == 0:
        raise RuntimeError("No valid balanced schedules")
    positive = sum(v for k, v in distribution.items() if k > 0)
    expected = sum(k * v for k, v in distribution.items()) / total
    return {
        "schedule_count": total,
        "net_distribution": {str(k): distribution[k] for k in sorted(distribution)},
        "positive_schedule_count": positive,
        "positive_schedule_fraction": positive / total,
        "exact_expected_net": expected,
        "balance_rule": "For each stream separately, A/B/C/D counts differ by at most one.",
        "same_slot_across_R1_R2_admissible": True,
    }


def _policy_cohort(
    cohort_name: str,
    backbone: list[dict[str, Any]],
    run_by_key: dict[str, dict[str, Any]],
    positive_threshold: float,
) -> dict[str, Any]:
    baseline_correct = sum(x["B0"]["answer"] == x["correct_answer"] for x in backbone)
    escalated = [x for x in backbone if x["theta_020_verifier_escalation"]]
    expected_repairs = Fraction(0)
    expected_harms = Fraction(0)
    expected_net = Fraction(0)
    item_pairs: list[list[tuple[int, int, int]]] = []
    per_item = []
    for item in escalated:
        qid = item["question_id"]
        truth = item["correct_answer"]
        b0 = item["B0"]["answer"]
        d0 = item["D0"]["answer"]
        by_stream_slot: dict[str, dict[str, str]] = {"R1": {}, "R2": {}}
        for stream in ("R1", "R2"):
            for placement_i in range(4):
                row = run_by_key[f"{qid}|P{placement_i}|{stream}"]
                by_stream_slot[stream][row["correct_display_slot"]] = row["parsed_answer"]
        pairs = []
        repair_n = harm_n = net_sum = 0
        for slot1_i, slot1 in enumerate(LETTERS):
            for slot2_i, slot2 in enumerate(LETTERS):
                final = majority3([d0, by_stream_slot["R1"][slot1], by_stream_slot["R2"][slot2]])
                repair = int(b0 != truth and final == truth)
                harm = int(b0 == truth and final != truth)
                delta = repair - harm
                repair_n += repair
                harm_n += harm
                net_sum += delta
                pairs.append((slot1_i, slot2_i, delta))
        expected_repairs += Fraction(repair_n, 16)
        expected_harms += Fraction(harm_n, 16)
        expected_net += Fraction(net_sum, 16)
        item_pairs.append(pairs)
        per_item.append({
            "question_id": qid,
            "uniform_pair_expected_net": net_sum / 16,
            "uniform_pair_repair_probability": repair_n / 16,
            "uniform_pair_harm_probability": harm_n / 16,
        })

    schedule = _balanced_schedule_distribution(item_pairs)
    closed_form_net = float(expected_net)
    survives = closed_form_net > 0 and schedule["positive_schedule_fraction"] >= positive_threshold
    return {
        "cohort": cohort_name,
        "n_items": len(backbone),
        "baseline_B0_correct_n": baseline_correct,
        "theta": 0.20,
        "routed_n": sum(x["theta_020_gate"] for x in backbone),
        "verifier_escalation_n": len(escalated),
        "closed_form_uniform_expected_repairs": float(expected_repairs),
        "closed_form_uniform_expected_harms": float(expected_harms),
        "closed_form_uniform_expected_net": closed_form_net,
        "closed_form_uniform_expected_strict_correct_n": baseline_correct + closed_form_net,
        "balanced_schedule_distribution": schedule,
        "positive_schedule_fraction_threshold": positive_threshold,
        "actuator_survives": survives,
        "kill_reasons": [
            reason
            for condition, reason in [
                (closed_form_net <= 0, "closed-form expected net is nonpositive"),
                (schedule["positive_schedule_fraction"] < positive_threshold, "fewer than the frozen fraction of balanced schedules have positive net"),
            ]
            if condition
        ],
        "per_escalated_item": per_item,
    }


def analyze(experiment_dir: Path, positive_threshold: float = 0.95) -> dict[str, Any]:
    runs = read_jsonl(experiment_dir / "runs.jsonl")
    if len(runs) != 568:
        raise RuntimeError(f"Full analysis requires 568 completed cells; observed {len(runs)}")
    run_by_key = {x["run_key"]: x for x in runs}
    if len(run_by_key) != 568:
        raise RuntimeError("Duplicate replay run_key")
    backbone = read_jsonl(experiment_dir / "frozen" / "policy_backbone.jsonl")
    primary_backbone = [x for x in backbone if x["primary_deduplicated_cohort"]]

    primary = _policy_cohort("deduplicated_942_primary", primary_backbone, run_by_key, positive_threshold)
    secondary = _policy_cohort("full_1000_secondary", backbone, run_by_key, positive_threshold)
    summary = {
        "schema_version": "ccrc.position_replay.analysis.v0.7.0",
        "experimental_base_cells": len(runs),
        "actual_model_calls": sum(int(x.get("model_call_count", 1)) for x in runs),
        "format_retry_calls": sum(int(x.get("model_call_count", 1)) - 1 for x in runs),
        "slot_effects": _slot_summary(runs),
        "within_item_slot_contrasts": _within_item_slot_contrasts(runs),
        "representation_instability": _representation_instability(runs),
        "policy_replay": {
            "primary": primary,
            "secondary": secondary,
            "forbidden_analysis_not_performed": "No majority or aggregation across all eight replay cells.",
        },
        "primary_decision": {
            "actuator_survives": primary["actuator_survives"],
            "kill_reasons": primary["kill_reasons"],
            "if_survives": "Topology qualifies for a fresh, powered confirmatory sample; this replay is not efficacy confirmation.",
            "if_killed": "Retire the current verifier actuator; do not tune theta or invent an eight-cell controller.",
        },
    }
    write_json(experiment_dir / "analysis.json", summary)

    with (experiment_dir / "cell_results.csv").open("w", encoding="utf-8", newline="") as f:
        fields = [
            "call_index", "run_key", "question_id", "placement", "replicate_stream",
            "correct_display_slot", "parsed_display_answer", "parsed_answer", "correct", "model_call_count",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in sorted(runs, key=lambda x: x["call_index"]):
            writer.writerow({k: row.get(k) for k in fields})
    return summary

