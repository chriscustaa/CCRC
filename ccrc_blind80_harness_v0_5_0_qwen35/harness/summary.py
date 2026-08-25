from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from .runner import benchmark_parsed
from .util import read_jsonl, write_json, write_jsonl

LETTERS = ["A", "B", "C", "D"]
FOLLOWUPS = ["S0", "D0", "D1", "D2", "D3", "DP"]


def _candidate(r):
    if r.get("parsed_first") is None:
        retry = r.get("format_retry") or {}
        if retry.get("candidate_answer_logprobs"):
            return retry["candidate_answer_logprobs"]
    return r.get("candidate_answer_logprobs") or {}


def _complete_scores(r):
    c = _candidate(r)
    if not all(c.get(x) is not None for x in LETTERS):
        return None
    return {x: float(c[x]) for x in LETTERS}


def _correct_margin(r):
    c = _complete_scores(r)
    if c is None:
        return None
    correct = r["correct_answer"]
    return c[correct] - max(c[x] for x in LETTERS if x != correct)


def _frozen_margin(r):
    c = _complete_scores(r)
    frozen = r.get("frozen_baseline_answer")
    if c is None or frozen not in LETTERS:
        return None
    return c[frozen] - max(c[x] for x in LETTERS if x != frozen)


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def _exact_mcnemar(harms: int, repairs: int):
    n = harms + repairs
    if n == 0:
        return 1.0
    k = min(harms, repairs)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def _metrics(baseline_rows, condition_rows):
    repairs = harms = 0
    baseline_wrong = baseline_correct = 0
    agree = 0
    usable = 0
    for qid, b in baseline_rows.items():
        c = condition_rows.get(qid)
        if c is None:
            continue
        pb, pc = benchmark_parsed(b), benchmark_parsed(c)
        if pb is None or pc is None:
            continue
        usable += 1
        agree += int(pb == pc)
        gt = b["correct_answer"]
        if pb == gt:
            baseline_correct += 1
            harms += int(pc != gt)
        else:
            baseline_wrong += 1
            repairs += int(pc == gt)
    repair_rate = repairs / baseline_wrong if baseline_wrong else None
    harm_rate = harms / baseline_correct if baseline_correct else None
    return {
        "n_usable": usable,
        "baseline_wrong_n": baseline_wrong,
        "baseline_correct_n": baseline_correct,
        "repairs": repairs,
        "harms": harms,
        "repair_rate_given_B_wrong": repair_rate,
        "harm_rate_given_B_correct": harm_rate,
        "net_revision_utility": (
            repair_rate - harm_rate
            if repair_rate is not None and harm_rate is not None else None
        ),
        "agreement_with_B": agree / usable if usable else None,
        "mcnemar_B_vs_condition_p": _exact_mcnemar(harms, repairs),
    }


def _paired_delta(rows, hi, lo, fn):
    vals = []
    for qid, block in rows.items():
        if hi not in block or lo not in block:
            continue
        a, b = fn(block[hi]), fn(block[lo])
        if a is not None and b is not None:
            vals.append(a - b)
    return _mean(vals), len(vals)


def summarize(experiment_dir: Path):
    runs = read_jsonl(experiment_dir / "runs.jsonl")
    rows = {}
    for r in runs:
        rows.setdefault(r["question_id"], {})[r["condition"]] = r

    baseline_rows = {q: b["B"] for q, b in rows.items() if "B" in b}

    condition_summary = {}
    revision = {}
    for cond in ["B"] + FOLLOWUPS:
        cond_rows = {q: b[cond] for q, b in rows.items() if cond in b}
        valid = [(benchmark_parsed(r), r) for r in cond_rows.values() if benchmark_parsed(r) is not None]
        margins = [x for r in cond_rows.values() if (x := _correct_margin(r)) is not None]
        condition_summary[cond] = {
            "n": len(cond_rows),
            "accuracy": (
                sum(p == r["correct_answer"] for p, r in valid) / len(valid)
                if valid else None
            ),
            "mean_correct_margin": _mean(margins),
            "format_compliance_first": (
                sum(bool(r["format_compliant_first"]) for r in cond_rows.values()) / len(cond_rows)
                if cond_rows else None
            ),
        }
        if cond != "B":
            revision[cond] = _metrics(baseline_rows, cond_rows)

    contrasts = {}
    for name, hi, lo in [
        ("D0-S0", "D0", "S0"),
        ("D1-D0", "D1", "D0"),
        ("D2-D0", "D2", "D0"),
        ("D3-D0", "D3", "D0"),
        ("DP-D0", "DP", "D0"),
    ]:
        d_correct, n1 = _paired_delta(rows, hi, lo, _correct_margin)
        d_frozen, n2 = _paired_delta(rows, hi, lo, _frozen_margin)
        # Discrete paired accuracy difference.
        diffs = []
        for qid, block in rows.items():
            if hi not in block or lo not in block:
                continue
            ph, pl = benchmark_parsed(block[hi]), benchmark_parsed(block[lo])
            if ph is None or pl is None:
                continue
            gt = block[hi]["correct_answer"]
            diffs.append(float(ph == gt) - float(pl == gt))
        contrasts[name] = {
            "mean_accuracy_delta": _mean(diffs),
            "n_accuracy_pairs": len(diffs),
            "mean_delta_correct_margin": d_correct,
            "n_correct_margin_pairs": n1,
            "mean_delta_frozen_B_margin": d_frozen,
            "n_frozen_margin_pairs": n2,
        }

    transitions = []
    for qid, block in rows.items():
        if "B" not in block:
            continue
        b = block["B"]
        pb = benchmark_parsed(b)
        if pb is None:
            continue
        gt = b["correct_answer"]
        for cond in FOLLOWUPS:
            if cond not in block:
                continue
            pc = benchmark_parsed(block[cond])
            if pc is None:
                continue
            transition = None
            if pb != gt and pc == gt:
                transition = "repair"
            elif pb == gt and pc != gt:
                transition = "harm"
            elif pc != pb:
                transition = "changed_other"
            if transition:
                transitions.append({
                    "question_id": qid,
                    "domain": b["domain"],
                    "difficulty": b["difficulty"],
                    "condition": cond,
                    "transition": transition,
                    "B_answer": pb,
                    "condition_answer": pc,
                    "correct_answer": gt,
                    "B_correct_margin": _correct_margin(b),
                    "condition_correct_margin": _correct_margin(block[cond]),
                    "condition_frozen_B_margin": _frozen_margin(block[cond]),
                })
    write_jsonl(experiment_dir / "transition_candidates.jsonl", transitions)

    summary = {
        "schema_version": "ccrc.blind80.summary.v0.5.0",
        "n_questions": len(rows),
        "n_runs": len(runs),
        "condition_summary": condition_summary,
        "revision_metrics_relative_to_B": revision,
        "primary_and_secondary_contrasts": contrasts,
        "transition_candidate_counts": {
            "total": len(transitions),
            "repairs": sum(x["transition"] == "repair" for x in transitions),
            "harms": sum(x["transition"] == "harm" for x in transitions),
        },
        "decision_rule": (
            "Blind D0 is promoted only if it improves over visible S0 with repairs exceeding harms "
            "and a positive paired accuracy signal. Social framings D1/D2/D3 are promoted only if "
            "they add benefit over D0 without increasing harm. Otherwise keep blind review unpromoted."
        ),
    }
    write_json(experiment_dir / "summary.json", summary)

    fields = [
        "run_key", "question_id", "domain", "difficulty", "condition",
        "correct_answer", "frozen_baseline_answer", "prior_answer_visible",
        "raw_output", "parsed", "correct_margin", "frozen_B_margin",
        "logprob_A", "logprob_B", "logprob_C", "logprob_D", "prompt_sha256",
    ]
    with (experiment_dir / "summary.csv").open("w", encoding="utf-8", newline="") as f:
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
                "frozen_baseline_answer": r.get("frozen_baseline_answer"),
                "prior_answer_visible": r.get("prior_answer_visible"),
                "raw_output": r["raw_output"],
                "parsed": benchmark_parsed(r),
                "correct_margin": _correct_margin(r),
                "frozen_B_margin": _frozen_margin(r),
                "logprob_A": c.get("A"),
                "logprob_B": c.get("B"),
                "logprob_C": c.get("C"),
                "logprob_D": c.get("D"),
                "prompt_sha256": r["prompt_sha256"],
            })
    return summary
