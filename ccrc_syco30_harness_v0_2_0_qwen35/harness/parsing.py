from __future__ import annotations

import re
from typing import Any

LETTER_RE = re.compile(r"\b([ABCD])\b")
EXACT_RE = re.compile(r"\s*[ABCDabcd]\s*\Z")


def parse_mcq_letter(text: str) -> str | None:
    hits = LETTER_RE.findall(text or "")
    if hits:
        return hits[-1]
    if EXACT_RE.fullmatch(text or ""):
        return (text or "").strip().upper()
    return None


def exact_one_letter(text: str) -> bool:
    return bool(EXACT_RE.fullmatch(text or ""))


def answer_candidate_logprobs(token_logprobs: list[dict[str, Any]] | None) -> dict[str, float | None]:
    out: dict[str, float | None] = {k: None for k in "ABCD"}
    if not token_logprobs:
        return out

    # First generated token is the decision position for the forced-choice prompt.
    first = token_logprobs[0]
    candidates = []
    if isinstance(first, dict):
        if "token" in first and "logprob" in first:
            candidates.append({"token": first["token"], "logprob": first["logprob"]})
        candidates.extend(first.get("top_logprobs") or [])

    for cand in candidates:
        token = str(cand.get("token", "")).strip().upper()
        if token in out:
            lp = cand.get("logprob")
            try:
                lp = float(lp)
            except (TypeError, ValueError):
                continue
            if out[token] is None or lp > out[token]:
                out[token] = lp
    return out
