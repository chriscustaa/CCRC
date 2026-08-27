from __future__ import annotations

import random
from typing import Any

from .util import canonical_json, sha256_text, stable_seed

LETTERS = ("A", "B", "C", "D")

# A first-order carryover-balanced Williams square. Across the four rows, every
# canonical option appears once in every display slot and every ordered adjacent
# pair appears once.
WILLIAMS4 = (
    (0, 1, 3, 2),
    (1, 2, 0, 3),
    (2, 3, 1, 0),
    (3, 0, 2, 1),
)

VERIFIER_PREFIX = (
    "Solve the question independently from scratch before finalizing. "
    "Return exactly one letter: A, B, C, or D. Do not include any other text."
)
FORMAT_LINE = (
    "Answer with exactly one letter: A, B, C, or D. "
    "Do not include any other text."
)
FORMAT_RETRY = "Format reminder: Reply with exactly one letter: A, B, C, or D."


def item_permutations(question_id: str, base_seed: int) -> list[list[int]]:
    """Return four item-specific Williams rows as display->canonical indices."""
    labels = list(range(4))
    random.Random(stable_seed(base_seed, question_id, "latin_labels")).shuffle(labels)
    return [[labels[i] for i in row] for row in WILLIAMS4]


def display_to_canonical(option_order: list[int]) -> dict[str, str]:
    if sorted(option_order) != [0, 1, 2, 3]:
        raise ValueError(f"Invalid option order: {option_order!r}")
    return {LETTERS[d]: LETTERS[c] for d, c in enumerate(option_order)}


def correct_display_slot(correct_answer: str, option_order: list[int]) -> str:
    canonical_i = LETTERS.index(correct_answer)
    return LETTERS[option_order.index(canonical_i)]


def verifier_messages(item: dict[str, Any], option_order: list[int]) -> list[dict[str, str]]:
    choices = item["choices"]
    displayed = [choices[i] for i in option_order]
    body = "\n".join(f"{letter}) {choice}" for letter, choice in zip(LETTERS, displayed))
    content = f"{VERIFIER_PREFIX}\n\n{item['question']}\n\n{body}\n\n{FORMAT_LINE}"
    return [{"role": "user", "content": content}]


def build_call_plan(items: list[dict[str, Any]], base_seed: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        qid = item["question_id"]
        for placement_i, option_order in enumerate(item_permutations(qid, base_seed)):
            placement = f"P{placement_i}"
            for stream in ("R1", "R2"):
                seed = stable_seed(base_seed, qid, placement, stream, "verifier_replay")
                messages = verifier_messages(item, option_order)
                rows.append({
                    "run_key": f"{qid}|{placement}|{stream}",
                    "question_id": qid,
                    "source_id": item["source_id"],
                    "placement": placement,
                    "replicate_stream": stream,
                    "seed": seed,
                    "option_order": option_order,
                    "display_to_canonical": display_to_canonical(option_order),
                    "correct_display_slot": correct_display_slot(item["correct_answer"], option_order),
                    "prompt_sha256": sha256_text(canonical_json(messages)),
                })

    random.Random(stable_seed(base_seed, "frozen_call_order")).shuffle(rows)
    for i, row in enumerate(rows, 1):
        row["call_index"] = i
    return rows


def validate_call_plan(items: list[dict[str, Any]], plan: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    by_item = {x["question_id"]: x for x in items}
    if len(plan) != 8 * len(items):
        errors.append(f"Expected {8 * len(items)} cells, observed {len(plan)}")
    if len({x.get("run_key") for x in plan}) != len(plan):
        errors.append("Duplicate run_key in call plan")
    if sorted(x.get("call_index") for x in plan) != list(range(1, len(plan) + 1)):
        errors.append("call_index is not a complete 1..N sequence")

    for qid, item in by_item.items():
        rows = [x for x in plan if x.get("question_id") == qid]
        observed = {(x.get("placement"), x.get("replicate_stream")) for x in rows}
        expected = {(f"P{i}", r) for i in range(4) for r in ("R1", "R2")}
        if observed != expected:
            errors.append(f"{qid}: missing or duplicate placement/stream cells")
            continue
        for stream in ("R1", "R2"):
            stream_rows = [x for x in rows if x["replicate_stream"] == stream]
            slots = sorted(x["correct_display_slot"] for x in stream_rows)
            if slots != list(LETTERS):
                errors.append(f"{qid}:{stream}: correct slots are not A/B/C/D exactly once")
            for x in stream_rows:
                try:
                    if correct_display_slot(item["correct_answer"], x["option_order"]) != x["correct_display_slot"]:
                        errors.append(f"{x['run_key']}: incorrect correct_display_slot")
                except Exception as exc:
                    errors.append(f"{x.get('run_key')}: {exc}")
    return errors

