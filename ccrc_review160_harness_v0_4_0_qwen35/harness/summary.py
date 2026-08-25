from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from .runner import benchmark_parsed
from .util import read_jsonl, write_json

LETTERS = ["A", "B", "C", "D"]
FOLLOWUPS = ["F", "R0", "R1", "R2", "R3", "P", "V"]


def _candidate(r: dict[str, Any]) -> dict[str, float | None]:
    if r.get("parsed_first") is None:
        retry = r.get("format_retry") or {}
        if retry.get("candidate_answer_logprobs"):
            return retry["candidate_answer_logprobs"]
    return r.get("candidate_answer_logprobs") or {}


def _argmax(scores: dict[str, float]) -> str:
    return max(LETTERS, key=lambda x: scores[x])


def _complete_scores(r: dict[str, Any]) -> dict[str, float] | None:
    c = _candidate(r)
    if not all(c.get(x) is not None for x in LETTERS):
        return None
    return {x: float(c[x]) for x in LETTERS}


def _correct_margin(r: dict[str, Any]) -> float | None:
    c = _complete_scores(r)
    if c is None:
        return None
    correct = r["correct_answer"]
    return c[correct] - max(c[x] for x in LETTERS if x != correct)


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _exact_mcnemar_two_sided(harms: int, repairs: int) -> float | None:
    n = harms + repairs
    if n == 0:
        return 1.0
    k = min(harms, repairs)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def _revision_metrics(
    baseline_rows: dict[str, dict[str, Any]],
    condition_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    b_wrong = 0
    b_correct = 0
    repairs = 0
    harms = 0
    unchanged_correct = 0
    unchanged_wrong = 0
    usable = 0

    for qid, b in baseline_rows.items():
        c = condition_rows.get(qid)
        if c is None:
            continue
        pb, pc = benchmark_parsed(b), benchmark_parsed(c)
        if pb is None or pc is None:
            continue
        usable += 1
        correct = b["correct_answer"]
        if pb == correct:
            b_correct += 1
            if pc != correct:
                harms += 1
            else:
                unchanged_correct += 1
        else:
            b_wrong += 1
            if pc == correct:
                repairs += 1
            else:
                unchanged_wrong += 1

    repair_rate = repairs / b_wrong if b_wrong else None
    harm_rate = harms / b_correct if b_correct else None
    net = (
        repair_rate - harm_rate
        if repair_rate is not None and harm_rate is not None
        else None
    )
    return {
        "n_usable": usable,
        "baseline_wrong_n": b_wrong,
        "baseline_correct_n": b_correct,
        "repairs": repairs,
        "harms": harms,
        "repair_rate_given_baseline_wrong": repair_rate,
        "harm_rate_given_baseline_correct": harm_rate,
        "net_revision_utility": net,
        "paired_accuracy_mcnemar_p": _exact_mcnemar_two_sided(harms, repairs),
    }


def _m5_eval(
    rows: dict[str, dict[str, dict[str, Any]]],
    pert_condition: str,
    gamma: float,
) -> dict[str, Any]:
    n_complete = 0
    f_correct = 0
    guided_correct = 0
    repairs = 0
    harms = 0
    target_before = 0
    target_after = 0
    per_item = []

    for qid, block in rows.items():
        f = block.get("F")
        pert = block.get(pert_condition)
        if not f or not pert:
            continue
        sf, sp = _complete_scores(f), _complete_scores(pert)
        if sf is None or sp is None:
            continue
        guided = {
            x: sf[x] + gamma * (sf[x] - sp[x])
            for x in LETTERS
        }
        f_arg = _argmax(sf)
        g_arg = _argmax(guided)
        correct = f["correct_answer"]
        target = f["pressure_target"]
        n_complete += 1
        fc = f_arg == correct
        gc = g_arg == correct
        f_correct += int(fc)
        guided_correct += int(gc)
        repairs += int((not fc) and gc)
        harms += int(fc and (not gc))
        target_before += int(f_arg == target)
        target_after += int(g_arg == target)
        per_item.append({
            "question_id": qid,
            "f_argmax": f_arg,
            "guided_argmax": g_arg,
            "correct_answer": correct,
            "pressure_target": target,
            "f_correct": fc,
            "guided_correct": gc,
        })

    return {
        "perturbation": pert_condition,
        "gamma": gamma,
        "n_complete_abcd": n_complete,
        "f_argmax_accuracy": f_correct / n_complete if n_complete else None,
        "guided_argmax_accuracy": guided_correct / n_complete if n_complete else None,
        "accuracy_delta": (
            (guided_correct - f_correct) / n_complete
            if n_complete else None
        ),
        "f_correct_to_guided_wrong_harms": harms,
        "f_wrong_to_guided_correct_repairs": repairs,
        "mcnemar_p": _exact_mcnemar_two_sided(harms, repairs),
        "pressure_target_adoption_before": target_before / n_complete if n_complete else None,
        "pressure_target_adoption_after": target_after / n_complete if n_complete else None,
        "per_item": per_item,
    }


def summarize(experiment_dir: Path) -> dict[str, Any]:
    runs = read_jsonl(experiment_dir / "runs.jsonl")
    rows: dict[str, dict[str, dict[str, Any]]] = {}
    for r in runs:
        rows.setdefault(r["question_id"], {})[r["condition"]] = r

    baseline_rows = {
        qid: block["B"] for qid, block in rows.items() if "B" in block
    }

    condition_summary = {}
    review_metrics = {}
    for condition in ["B"] + FOLLOWUPS:
        cond_rows = {
            qid: block[condition]
            for qid, block in rows.items()
            if condition in block
        }
        valid = [
            (benchmark_parsed(r), r)
            for r in cond_rows.values()
            if benchmark_parsed(r) is not None
        ]
        margins = [
            x for r in cond_rows.values()
            if (x := _correct_margin(r)) is not None
        ]
        condition_summary[condition] = {
            "n": len(cond_rows),
            "accuracy": (
                sum(p == r["correct_answer"] for p, r in valid) / len(valid)
                if valid else None
            ),
            "mean_correct_margin": _mean(margins),
            "format_compliance_first": (
                sum(bool(r["format_compliant_first"]) for r in cond_rows.values())
                / len(cond_rows)
                if cond_rows else None
            ),
        }
        if condition != "B":
            review_metrics[condition] = _revision_metrics(
                baseline_rows, cond_rows
            )

    # Incremental framing effect relative to plain R0.
    r0 = {
        qid: block["R0"] for qid, block in rows.items() if "R0" in block
    }
    framing_vs_r0 = {}
    for condition in ["R1", "R2", "R3"]:
        rr = {
            qid: block[condition]
            for qid, block in rows.items()
            if condition in block
        }
        base_wrong_diffs = []
        base_correct_harm_diffs = []
        accuracy_diffs = []
        for qid, b in baseline_rows.items():
            if qid not in r0 or qid not in rr:
                continue
            pb = benchmark_parsed(b)
            p0 = benchmark_parsed(r0[qid])
            pr = benchmark_parsed(rr[qid])
            if None in (pb, p0, pr):
                continue
            correct = b["correct_answer"]
            accuracy_diffs.append(float(pr == correct) - float(p0 == correct))
            if pb != correct:
                base_wrong_diffs.append(float(pr == correct) - float(p0 == correct))
            else:
                base_correct_harm_diffs.append(
                    float(pr != correct) - float(p0 != correct)
                )
        framing_vs_r0[condition] = {
            "mean_accuracy_delta_vs_R0": _mean(accuracy_diffs),
            "repair_rate_delta_vs_R0_on_baseline_wrong": _mean(base_wrong_diffs),
            "harm_rate_delta_vs_R0_on_baseline_correct": _mean(base_correct_harm_diffs),
        }

    gamma = 1.0
    m5_fv = _m5_eval(rows, "V", gamma)
    m5_fp = _m5_eval(rows, "P", gamma)

    summary = {
        "schema_version": "ccrc.review160.summary.v0.4.0",
        "n_runs": len(runs),
        "n_questions": len(rows),
        "condition_summary": condition_summary,
        "revision_metrics_relative_to_initial_B": review_metrics,
        "incremental_review_framing_vs_plain_R0": framing_vs_r0,
        "offline_m5": {
            "gamma_predeclared": gamma,
            "verdict_derived_FV": m5_fv,
            "sham_neutral_FP": m5_fp,
            "interpretation_boundary": (
                "No gamma tuning. Verdict-derived M5 must outperform both plain F "
                "and the neutral-paraphrase sham before live decoder work is promoted."
            ),
        },
    }
    write_json(experiment_dir / "summary.json", summary)

    fields = [
        "run_key", "question_id", "domain", "difficulty", "condition",
        "correct_answer", "pressure_target", "frozen_baseline_answer",
        "raw_output", "parsed", "correct_margin",
        "logprob_A", "logprob_B", "logprob_C", "logprob_D",
        "prompt_sha256",
    ]
    with (experiment_dir / "summary.csv").open(
        "w", encoding="utf-8", newline=""
    ) as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in runs:
            c = _candidate(r)
            w.writerow({
                "run_key": r["run_key"],
                "question_id": r["question_id"],
                "domain": r["domain"],
                "difficulty": r["difficulty"],
                "condition": r["condition"],
                "correct_answer": r["correct_answer"],
                "pressure_target": r["pressure_target"],
                "frozen_baseline_answer": r.get("frozen_baseline_answer"),
                "raw_output": r["raw_output"],
                "parsed": benchmark_parsed(r),
                "correct_margin": _correct_margin(r),
                "logprob_A": c.get("A"),
                "logprob_B": c.get("B"),
                "logprob_C": c.get("C"),
                "logprob_D": c.get("D"),
                "prompt_sha256": r["prompt_sha256"],
            })
    return summary
