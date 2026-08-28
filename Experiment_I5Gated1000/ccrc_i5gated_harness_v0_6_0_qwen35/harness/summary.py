from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from typing import Any

from .policy import policy_decision


def _exact_mcnemar(a: list[bool], b: list[bool]) -> dict[str, Any]:
    b_only = sum((not x) and y for x, y in zip(a, b))
    a_only = sum(x and (not y) for x, y in zip(a, b))
    n = b_only + a_only
    if n == 0:
        p = 1.0
    else:
        k = min(b_only, a_only)
        tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
        p = min(1.0, 2 * tail)
    return {"b_correct_a_wrong": b_only, "a_correct_b_wrong": a_only, "discordant_n": n, "exact_p": p}


def _bootstrap(values: list[float], *, seed: int, iterations: int = 10000) -> dict[str, float]:
    if not values:
        return {"mean": 0.0, "ci95_low": 0.0, "ci95_high": 0.0}
    r = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(iterations):
        means.append(sum(values[r.randrange(n)] for _ in range(n)) / n)
    means.sort()
    lo = means[int(0.025 * iterations)]
    hi = means[min(iterations - 1, int(0.975 * iterations))]
    return {"mean": sum(values) / n, "ci95_low": lo, "ci95_high": hi}


def _paired_condition_contrast(items, by_q, left: str, right: str, *, seed: int) -> dict[str, Any]:
    left_correct, right_correct, deltas = [], [], []
    repairs = harms = 0
    for item in items:
        q = by_q[item["question_id"]]
        gt = item["correct_answer"]
        lc = bool(q.get(left) and q[left].get("parsed_answer") == gt)
        rc = bool(q.get(right) and q[right].get("parsed_answer") == gt)
        left_correct.append(lc); right_correct.append(rc); deltas.append(float(rc) - float(lc))
        repairs += (not lc and rc); harms += (lc and not rc)
    return {
        "left": left, "right": right,
        "delta_accuracy_right_minus_left": sum(deltas) / len(deltas),
        "repairs": repairs, "harms": harms, "net_repairs": repairs - harms,
        "mcnemar": _exact_mcnemar(left_correct, right_correct),
        "bootstrap": _bootstrap(deltas, seed=seed),
    }


def summarize(items: list[dict[str, Any]], runs: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    by_q: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in runs:
        by_q[row["question_id"]][row["condition"]] = row
    seed = int(cfg["seed"])
    thresholds = [float(x) for x in (cfg.get("controller") or {}).get("thresholds", [0.20, 0.50])]

    core_summary = {}
    for condition in ("B0", "B5", "D0", "D5"):
        vals = [by_q[i["question_id"]].get(condition) for i in items]
        valid = [r for r in vals if r and isinstance(r.get("parsed_answer"), str) and r.get("parsed_answer") in "ABCD"]
        correct = sum(r["parsed_answer"] == r["correct_answer"] for r in valid)
        core_summary[condition] = {
            "valid_n": len(valid), "correct_n": correct,
            "accuracy": correct / len(valid) if valid else None,
            "format_retry_n": sum(bool(r.get("format_retry_used")) for r in valid),
            "sensor_missing_n": sum(r.get("sensor_gap") is None for r in valid) if condition.startswith("B") else None,
        }

    b0_correct, b5_correct = [], []
    i5_item_deltas = []
    i5_repairs = i5_harms = 0
    for item in items:
        q = by_q[item["question_id"]]
        gt = item["correct_answer"]
        c0 = bool(q.get("B0") and q["B0"].get("parsed_answer") == gt)
        c5 = bool(q.get("B5") and q["B5"].get("parsed_answer") == gt)
        b0_correct.append(c0); b5_correct.append(c5); i5_item_deltas.append(float(c5) - float(c0))
        i5_repairs += (not c0 and c5); i5_harms += (c0 and not c5)

    direct_i5 = {
        "delta_accuracy": sum(i5_item_deltas) / len(i5_item_deltas),
        "repairs": i5_repairs, "harms": i5_harms, "net_repairs": i5_repairs - i5_harms,
        "mcnemar": _exact_mcnemar(b0_correct, b5_correct),
        "bootstrap": _bootstrap(i5_item_deltas, seed=seed + 610),
    }

    direct_contrasts = {
        "D0_minus_B0": _paired_condition_contrast(items, by_q, "B0", "D0", seed=seed + 620),
        "D5_minus_B5": _paired_condition_contrast(items, by_q, "B5", "D5", seed=seed + 621),
        "D5_minus_D0": _paired_condition_contrast(items, by_q, "D0", "D5", seed=seed + 622),
    }

    controllers: dict[str, Any] = {}
    item_policy: dict[tuple[str, float], list[dict[str, Any]]] = {}
    for arm, bname, dname in (("I5_OFF", "B0", "D0"), ("I5_ON", "B5", "D5")):
        for theta in thresholds:
            results = []
            for item in items:
                q = by_q[item["question_id"]]
                b, d = q.get(bname), q.get(dname)
                v1, v2 = q.get("V1"), q.get("V2")
                decision = policy_decision(
                    baseline=b.get("parsed_answer") if b else None,
                    blind=d.get("parsed_answer") if d else None,
                    v1=v1.get("parsed_answer") if v1 else None,
                    v2=v2.get("parsed_answer") if v2 else None,
                    gap=b.get("sensor_gap") if b else None,
                    theta=theta,
                )
                gt = item["correct_answer"]
                base_correct = bool(b and b.get("parsed_answer") == gt)
                final_correct = decision["answer"] == gt
                results.append({**decision, "base_correct": base_correct, "final_correct": final_correct, "qid": item["question_id"]})
            item_policy[(arm, theta)] = results
            n = len(results)
            covered = [x for x in results if x["answer"] is not None]
            repairs = sum((not x["base_correct"]) and x["final_correct"] for x in results)
            harms = sum(x["base_correct"] and (not x["final_correct"]) for x in results)
            strict_delta = [float(x["final_correct"]) - float(x["base_correct"]) for x in results]
            key = f"{arm}_theta_{theta:.2f}"
            controllers[key] = {
                "theta": theta,
                "n": n,
                "routed_n": sum(x["routed"] for x in results),
                "route_rate": sum(x["routed"] for x in results) / n,
                "verifier_escalation_n": sum(x["used_v"] for x in results),
                "abstention_n": sum(x["answer"] is None for x in results),
                "strict_correct_n": sum(x["final_correct"] for x in results),
                "strict_accuracy": sum(x["final_correct"] for x in results) / n,
                "coverage": len(covered) / n,
                "selective_accuracy": sum(x["final_correct"] for x in covered) / len(covered) if covered else None,
                "repairs": repairs, "harms": harms, "net_repairs": repairs - harms,
                "production_equivalent_d_calls": sum(x["used_d"] for x in results),
                "production_equivalent_v_calls": 2 * sum(x["used_v"] for x in results),
                "production_equivalent_total_calls": n + sum(x["used_d"] for x in results) + 2 * sum(x["used_v"] for x in results),
                "delta_accuracy_vs_baseline": sum(strict_delta) / n,
                "bootstrap_delta": _bootstrap(strict_delta, seed=seed + int(theta * 1000) + (5 if arm == "I5_ON" else 0)),
                "decision_reasons": dict(Counter(x["reason"] for x in results)),
            }

    interactions = {}
    for theta in thresholds:
        off = item_policy[("I5_OFF", theta)]
        on = item_policy[("I5_ON", theta)]
        controller_i5 = [float(y["final_correct"]) - float(x["final_correct"]) for x, y in zip(off, on)]
        interaction = [controller_i5[i] - i5_item_deltas[i] for i in range(len(items))]
        interactions[f"theta_{theta:.2f}"] = {
            "i5_effect_inside_controller": _bootstrap(controller_i5, seed=seed + 700 + int(theta * 100)),
            "interaction_vs_direct_i5": _bootstrap(interaction, seed=seed + 800 + int(theta * 100)),
        }

    verifier_rows = []
    for item in items:
        q = by_q[item["question_id"]]
        if q.get("V1") and q.get("V2"):
            v1, v2 = q["V1"].get("parsed_answer"), q["V2"].get("parsed_answer")
            verifier_rows.append({"agree": isinstance(v1, str) and v1 == v2 and v1 in "ABCD", "v1_correct": v1 == item["correct_answer"], "v2_correct": v2 == item["correct_answer"]})
    agree_n = sum(x["agree"] for x in verifier_rows)
    agree_correct = sum(x["agree"] and x["v1_correct"] for x in verifier_rows)
    disagree_n = sum(not x["agree"] for x in verifier_rows)
    verifier_diag = {
        "items_n": len(verifier_rows),
        "v1_v2_agree_n": agree_n,
        "agree_both_correct_n": agree_correct,
        "agree_accuracy": agree_correct / agree_n if agree_n else None,
        "disagree_n": disagree_n,
        "disagree_v1_accuracy": sum((not x["agree"]) and x["v1_correct"] for x in verifier_rows) / disagree_n if disagree_n else None,
        "disagree_v2_accuracy": sum((not x["agree"]) and x["v2_correct"] for x in verifier_rows) / disagree_n if disagree_n else None,
    }

    actual_calls = sum(int(r.get("model_call_count", 1)) for r in runs)
    return {
        "schema_version": "ccrc.i5gated.summary.v0.6.0",
        "experiment_id": cfg["experiment_id"],
        "n": len(items),
        "core": core_summary,
        "direct_i5": direct_i5,
        "direct_contrasts": direct_contrasts,
        "controllers": controllers,
        "interactions": interactions,
        "verifier_diagnostic": verifier_diag,
        "actual_experimental_calls": actual_calls,
        "interpretation_guardrail": "Production-equivalent D/V calls are reported separately from unconditional experimental calls.",
    }
