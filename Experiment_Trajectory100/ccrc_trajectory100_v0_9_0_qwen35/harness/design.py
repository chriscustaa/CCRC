from __future__ import annotations

import random
from typing import Any

from .util import canonical_json, sha256_text, stable_seed

LETTERS = ("A", "B", "C", "D")
STAGES = ("T0", "T1", "T2", "T3", "T4")

STAGE_INSTRUCTIONS = {
    "T0": "",
    "T1": (
        "Silently check the givens and identify exactly what the question is asking "
        "before choosing the best answer."
    ),
    "T2": (
        "Silently solve the problem independently from first principles and check each "
        "answer choice before choosing the best answer."
    ),
    "T3": (
        "Silently challenge the most tempting answer: look for a counterexample, hidden "
        "assumption, exception, or misleading distractor before choosing the best answer."
    ),
    "T4": (
        "Silently make a final synthesis: reconcile the direct solution, the alternative "
        "choices, and possible objections before choosing the best answer."
    ),
}

FORMAT_LINE = (
    "Answer with exactly one letter: A, B, C, or D. "
    "Do not include any other text."
)
FORMAT_RETRY = "Format reminder: Reply with exactly one letter: A, B, C, or D."


def stage_messages(item: dict[str, Any], stage: str) -> list[dict[str, str]]:
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage}")
    choices = item["choices"]
    body = "\n".join(f"{letter}) {choice}" for letter, choice in zip(LETTERS, choices))
    parts = []
    instruction = STAGE_INSTRUCTIONS[stage]
    if instruction:
        parts.append(instruction)
    parts.extend([item["question"], body, FORMAT_LINE])
    return [{"role": "user", "content": "\n\n".join(parts)}]


def build_call_plan(items: list[dict[str, Any]], base_seed: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        qid = item["question_id"]
        for stage_i, stage in enumerate(STAGES):
            messages = stage_messages(item, stage)
            rows.append({
                "run_key": f"{qid}|{stage}",
                "question_id": qid,
                "source_bundle": item["source_bundle"],
                "stage": stage,
                "stage_index": stage_i,
                "seed": stable_seed(base_seed, qid, stage, "trajectory100"),
                "prompt_sha256": sha256_text(canonical_json(messages)),
            })

    # Calls are stateless, so balance runtime drift across stages instead of executing
    # all depth levels in a fixed chronological block.
    random.Random(stable_seed(base_seed, "trajectory100_call_order")).shuffle(rows)
    for i, row in enumerate(rows, 1):
        row["call_index"] = i
    return rows


def validate_call_plan(items: list[dict[str, Any]], plan: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    expected_n = len(items) * len(STAGES)
    if len(plan) != expected_n:
        errors.append(f"Expected {expected_n} cells, observed {len(plan)}")
    if len({x.get("run_key") for x in plan}) != len(plan):
        errors.append("Duplicate run_key in call plan")
    if sorted(x.get("call_index") for x in plan) != list(range(1, len(plan) + 1)):
        errors.append("call_index is not a complete 1..N sequence")
    by_id = {x["question_id"]: x for x in items}
    if len(by_id) != len(items):
        errors.append("Duplicate question_id in frozen items")
    for qid, item in by_id.items():
        rows = [x for x in plan if x.get("question_id") == qid]
        if sorted(x.get("stage") for x in rows) != list(STAGES):
            errors.append(f"{qid}: stages are not exactly T0..T4")
            continue
        for row in rows:
            expected = stage_messages(item, row["stage"])
            if sha256_text(canonical_json(expected)) != row.get("prompt_sha256"):
                errors.append(f"{row.get('run_key')}: frozen prompt hash mismatch")
    return errors
