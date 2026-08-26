from __future__ import annotations

from collections import Counter
from typing import Any


def answer_gap(candidate_logprobs: dict[str, float | None] | None) -> float | None:
    if not candidate_logprobs:
        return None
    vals = []
    for letter in "ABCD":
        value = candidate_logprobs.get(letter)
        if value is None:
            return None
        vals.append(float(value))
    vals.sort(reverse=True)
    return vals[0] - vals[1]


def majority3(a: str | None, b: str | None, c: str | None) -> str | None:
    vals = [x for x in (a, b, c) if isinstance(x, str) and x in "ABCD"]
    if len(vals) != 3:
        return None
    counts = Counter(vals)
    winner, count = counts.most_common(1)[0]
    return winner if count >= 2 else None


def policy_decision(
    *,
    baseline: str | None,
    blind: str | None,
    v1: str | None,
    v2: str | None,
    gap: float | None,
    theta: float,
) -> dict[str, Any]:
    if not isinstance(baseline, str) or baseline not in "ABCD":
        return {"answer": None, "reason": "baseline_invalid", "routed": True, "used_d": False, "used_v": False}
    if gap is not None and gap >= theta:
        return {"answer": baseline, "reason": "high_margin_release", "routed": False, "used_d": False, "used_v": False}
    if not isinstance(blind, str) or blind not in "ABCD":
        return {"answer": None, "reason": "blind_invalid", "routed": True, "used_d": True, "used_v": False}
    if blind == baseline:
        return {"answer": blind, "reason": "blind_consensus", "routed": True, "used_d": True, "used_v": False}
    final = majority3(blind, v1, v2)
    if final is None:
        return {"answer": None, "reason": "verifier_no_majority", "routed": True, "used_d": True, "used_v": True}
    return {"answer": final, "reason": "blind_verifier_majority", "routed": True, "used_d": True, "used_v": True}
