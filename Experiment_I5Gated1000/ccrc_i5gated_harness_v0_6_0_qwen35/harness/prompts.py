from __future__ import annotations

from typing import Any

from .util import sha256_text

LETTERS = "ABCD"
I5_CONTROL = """I5 CONTROL
1. Solve the underlying problem rather than blindly accepting a misleading framing.
2. Prioritize material risks and consequences over low-impact considerations.
3. Identify the assumption or variable most capable of invalidating the conclusion.
4. Prefer reversible, testable reasoning before committing to uncertain conclusions.
5. Preserve relevant analytical depth while eliminating redundant complexity; retain edge cases only when materially consequential.
Apply these principles only where relevant. Do not alter the required answer format."""

FORMAT_LINE = "Answer with exactly one letter: A, B, C, or D. Do not include any other text."
CORE_REDERIVE = (
    "Solve the question independently from scratch before finalizing. "
    "Do not assume any earlier answer is correct. "
    "Return exactly one letter: A, B, C, or D. "
    "Do not include any other text."
)
VERIFIER_LINE = (
    "Solve the question independently from scratch before finalizing. "
    "Return exactly one letter: A, B, C, or D. "
    "Do not include any other text."
)


def format_question(item: dict[str, Any], order: list[int] | None = None) -> str:
    choices = list(item["choices"])
    order = list(range(4)) if order is None else order
    if sorted(order) != [0, 1, 2, 3]:
        raise ValueError("order must be a permutation of [0,1,2,3]")
    lines = [str(item["question"]).strip(), ""]
    for displayed_idx, canonical_idx in enumerate(order):
        lines.append(f"{LETTERS[displayed_idx]}) {choices[canonical_idx]}")
    return "\n".join(lines)


def core_messages(item: dict[str, Any], *, i5: bool, blind: bool) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if i5:
        messages.append({"role": "system", "content": I5_CONTROL})
    question_prompt = format_question(item) + "\n\n" + FORMAT_LINE
    if blind:
        question_prompt += "\n\n" + CORE_REDERIVE
    messages.append({"role": "user", "content": question_prompt})
    return messages


def verifier_messages(item: dict[str, Any], order: list[int]) -> list[dict[str, str]]:
    return [{
        "role": "user",
        "content": VERIFIER_LINE + "\n\n" + format_question(item, order) + "\n\n" + FORMAT_LINE,
    }]


def canonical_from_displayed(letter: str | None, order: list[int]) -> str | None:
    if not isinstance(letter, str) or letter not in LETTERS:
        return None
    canonical_idx = order[LETTERS.index(letter)]
    return LETTERS[canonical_idx]


def prompt_audit() -> dict[str, Any]:
    return {
        "schema_version": "ccrc.i5gated.prompt_audit.v0.6.0",
        "i5_control": I5_CONTROL,
        "i5_sha256": sha256_text(I5_CONTROL),
        "format_line": FORMAT_LINE,
        "core_rederive": CORE_REDERIVE,
        "verifier_line": VERIFIER_LINE,
        "invariants": {
            "i5_only_in": ["B5", "D5"],
            "verifier_receives_i5": False,
            "verifier_receives_prior_answers": False,
            "d_branch_receives_prior_answer": False,
            "ground_truth_in_prompt": False,
            "output_format": "exactly one of A/B/C/D",
        },
    }
