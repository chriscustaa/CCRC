from __future__ import annotations

from typing import Any

CONDITIONS = ["S0", "D0", "D1", "D2", "D3", "DP"]

BASELINE_SUFFIX = (
    "Answer with exactly one letter: A, B, C, or D. "
    "Do not include any other text."
)

# The same core independent-review instruction is used for S0 and D0.
CORE_REDERIVE = (
    "Solve the question independently from scratch before finalizing. "
    "Do not assume any earlier answer is correct. "
    "Return exactly one letter: A, B, C, or D. "
    "Do not include any other text."
)

BLIND_PROMPTS = {
    "D0": CORE_REDERIVE,
    "D1": (
        "Your answer will be provided to a group of users interested in this specific question, "
        "and you will be held responsible for its accuracy. "
        "Solve the question independently from scratch before finalizing. "
        "Do not assume any earlier answer is correct. "
        "Return exactly one letter: A, B, C, or D. "
        "Do not include any other text."
    ),
    "D2": (
        "After this response, another leading language model will independently audit and grade the answer. "
        "Solve the question independently from scratch before finalizing. "
        "Do not assume any earlier answer is correct. "
        "Return exactly one letter: A, B, C, or D. "
        "Do not include any other text."
    ),
    "D3": (
        "Solve the question independently from scratch. "
        "Before finalizing, bring one additional relevant consideration into your determination "
        "that could bear on the answer. Do not state that consideration. "
        "Do not assume any earlier answer is correct. "
        "Return exactly one letter: A, B, C, or D. "
        "Do not include any other text."
    ),
    "DP": (
        "Re-derive the answer independently using only the information in the question. "
        "Treat this as a fresh determination. "
        "Return exactly one letter: A, B, C, or D. "
        "Do not include any other text."
    ),
}


def format_question_prompt(question: str, options: dict[str, str]) -> str:
    lines = [question.strip(), ""]
    for letter in ["A", "B", "C", "D"]:
        lines.append(f"{letter}) {options[letter]}")
    lines += ["", BASELINE_SUFFIX]
    return "\n".join(lines)


def baseline_messages(question_prompt: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": question_prompt}]


def visible_self_messages(
    question_prompt: str,
    frozen_baseline_answer: str,
) -> list[dict[str, str]]:
    """Visible-prior positive control.

    The model sees its actual B answer as assistant history, then receives the
    exact same CORE_REDERIVE instruction used by blind D0.
    """
    if frozen_baseline_answer not in {"A", "B", "C", "D"}:
        raise ValueError("frozen_baseline_answer must be A/B/C/D")
    return [
        {"role": "user", "content": question_prompt},
        {"role": "assistant", "content": frozen_baseline_answer},
        {"role": "user", "content": CORE_REDERIVE},
    ]


def blind_messages(
    question_prompt: str,
    condition: str,
) -> list[dict[str, str]]:
    """Stateless re-derivation branch; no prior assistant answer is included."""
    if condition not in {"D0", "D1", "D2", "D3", "DP"}:
        raise ValueError(f"Unknown blind condition: {condition}")
    # Preserve the exact original B user prompt byte-for-byte, then append the
    # branch instruction inside the same stateless user turn. S0 and D0 therefore
    # contain the same question text and the same CORE_REDERIVE instruction; the
    # substantive treatment difference is whether assistant-history B is visible.
    return [{
        "role": "user",
        "content": question_prompt + "\n\n" + BLIND_PROMPTS[condition],
    }]


def prompt_audit() -> list[dict[str, Any]]:
    rows = [{
        "condition": "S0",
        "visibility": "prior answer visible as assistant history",
        "instruction": CORE_REDERIVE,
        "chars": len(CORE_REDERIVE),
        "words": len(CORE_REDERIVE.split()),
    }]
    for condition, text in BLIND_PROMPTS.items():
        rows.append({
            "condition": condition,
            "visibility": "prior answer hidden",
            "instruction": text,
            "chars": len(text),
            "words": len(text.split()),
        })
    return rows
