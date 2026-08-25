from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .util import sha256_text, stable_seed

OPTION_RE = re.compile(r"^\s*([ABCD])\)\s*(.*)\s*$")

PINNED_DATASET_URL = (
    "https://raw.githubusercontent.com/debu-sinha/"
    "sycobench-600/v1.0.1/data/questions.json"
)


def normalize_question(q: dict[str, Any]) -> dict[str, Any]:
    out = dict(q)
    if isinstance(out["options"], list):
        opts = {}
        for raw in out["options"]:
            m = OPTION_RE.match(str(raw))
            if not m:
                raise ValueError(f"Bad option format for {out.get('id')}: {raw!r}")
            opts[m.group(1)] = m.group(2).strip()
        out["options"] = opts
    if set(out["options"]) != {"A", "B", "C", "D"}:
        raise ValueError(f"Bad options for {out.get('id')}")
    if out["correct"] not in {"A", "B", "C", "D"}:
        raise ValueError(f"Bad correct letter for {out.get('id')}")
    return out


def load_questions(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        raise ValueError("Expected SycoBench questions.json to be a JSON array")
    return [normalize_question(q) for q in raw]


def canonical_stem(text: str) -> str:
    return " ".join(text.lower().split())


def select_balanced_unique(
    questions: list[dict[str, Any]], n: int, seed: int
) -> list[dict[str, Any]]:
    if n <= 0:
        raise ValueError("n must be positive")

    domains = sorted({q.get("domain") for q in questions})
    difficulties = sorted({q.get("difficulty") for q in questions})
    if None in domains or None in difficulties:
        raise ValueError("All selected questions must have domain and difficulty")

    rng = random.Random(seed)
    domain_order = list(domains)
    rng.shuffle(domain_order)

    base = n // len(domain_order)
    rem = n % len(domain_order)
    domain_quota = {
        d: base + (1 if i < rem else 0) for i, d in enumerate(domain_order)
    }

    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for q in questions:
        buckets[(q["domain"], q["difficulty"])].append(q)

    for key, vals in buckets.items():
        rr = random.Random(stable_seed(seed, *key))
        rr.shuffle(vals)

    selected: list[dict[str, Any]] = []
    seen_stems: set[str] = set()

    for domain in domain_order:
        quota = domain_quota[domain]
        diff_order = list(difficulties)
        random.Random(stable_seed(seed, domain, "difficulty_order")).shuffle(diff_order)

        per_diff = quota // len(diff_order)
        extra = quota % len(diff_order)
        diff_quota = {
            diff: per_diff + (1 if i < extra else 0)
            for i, diff in enumerate(diff_order)
        }

        chosen_domain = []
        for diff in diff_order:
            want = diff_quota[diff]
            for q in buckets.get((domain, diff), []):
                stem = canonical_stem(q["question"])
                if stem in seen_stems:
                    continue
                chosen_domain.append(q)
                seen_stems.add(stem)
                if sum(1 for x in chosen_domain if x["difficulty"] == diff) >= want:
                    break

        # Fill any domain shortfall from remaining difficulty buckets.
        if len(chosen_domain) < quota:
            pool = [
                q for q in questions
                if q["domain"] == domain and canonical_stem(q["question"]) not in seen_stems
            ]
            random.Random(stable_seed(seed, domain, "fill")).shuffle(pool)
            for q in pool:
                chosen_domain.append(q)
                seen_stems.add(canonical_stem(q["question"]))
                if len(chosen_domain) == quota:
                    break

        if len(chosen_domain) != quota:
            raise ValueError(f"Could not fill quota for domain={domain}: {len(chosen_domain)}/{quota}")

        selected.extend(chosen_domain)

    # Stable final randomization so domain blocks are not execution/order blocks.
    random.Random(stable_seed(seed, "final_order")).shuffle(selected)

    if len(selected) != n:
        raise AssertionError(f"Expected {n} items, got {len(selected)}")
    if len({canonical_stem(q["question"]) for q in selected}) != n:
        raise AssertionError("Duplicate exact question stem in selected set")

    out = []
    for i, q in enumerate(selected, 1):
        out.append({
            "task_id": f"T{i:03d}",
            "source_id": q["id"],
            "domain": q["domain"],
            "difficulty": q["difficulty"],
            "question": q["question"],
            "options": q["options"],
            "correct": q["correct"],
            "source_reasoning": q.get("reasoning"),
            "stem_sha256": sha256_text(canonical_stem(q["question"])),
        })
    return out



def _apportion_with_caps(
    capacities: dict[str, int],
    total: int,
    seed: int,
    label: str,
) -> dict[str, int]:
    """Hamilton-style proportional apportionment, capped by available capacity."""
    if total < 0 or total > sum(capacities.values()):
        raise ValueError(
            f"Cannot apportion total={total} across capacity={sum(capacities.values())}"
        )
    if total == 0:
        return {k: 0 for k in capacities}

    keys = sorted(k for k, v in capacities.items() if v > 0)
    cap_total = sum(capacities[k] for k in keys)
    exact = {k: total * capacities[k] / cap_total for k in keys}
    quota = {k: min(capacities[k], int(exact[k])) for k in keys}

    left = total - sum(quota.values())
    # Largest remainder; stable seeded hash breaks exact ties.
    def tie(k: str) -> int:
        return stable_seed(seed, label, k)

    while left > 0:
        candidates = [
            k for k in keys if quota[k] < capacities[k]
        ]
        if not candidates:
            raise ValueError("Capacity exhausted during apportionment")
        candidates.sort(
            key=lambda k: (exact[k] - int(exact[k]), -tie(k)),
            reverse=True,
        )
        for k in candidates:
            if left == 0:
                break
            if quota[k] < capacities[k]:
                quota[k] += 1
                left -= 1
    return {k: quota.get(k, 0) for k in capacities}


def select_balanced_unique_excluding(
    questions: list[dict[str, Any]],
    n: int,
    seed: int,
    exclude_ids: set[str] | None = None,
    exclude_stems: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Select a fresh held-out sample with semantic-stem independence.

    SycoBench contains option-permuted repetitions of some semantic stems. After
    excluding prior stems, equal per-domain quotas can be impossible. This
    selector therefore:
      1) removes excluded source IDs and canonical stems;
      2) chooses one deterministic representative per remaining semantic stem;
      3) apportions the requested sample across domains proportional to available
         unique-stem capacity;
      4) apportions each domain quota across difficulty labels proportionally;
      5) shuffles deterministically.

    This preserves held-out semantic independence rather than reusing a prior
    question with merely permuted answer options.
    """
    if n <= 0:
        raise ValueError("n must be positive")
    exclude_ids = exclude_ids or set()
    exclude_stems = exclude_stems or set()

    eligible = [
        q for q in questions
        if q["id"] not in exclude_ids
        and canonical_stem(q["question"]) not in exclude_stems
    ]

    # One deterministic source row per semantic stem.
    by_stem: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for q in eligible:
        by_stem[canonical_stem(q["question"])].append(q)

    representatives: list[dict[str, Any]] = []
    for stem, rows in sorted(by_stem.items()):
        rr = random.Random(stable_seed(seed, "stem_rep", sha256_text(stem)))
        rows = list(rows)
        rr.shuffle(rows)
        representatives.append(rows[0])

    if len(representatives) < n:
        raise ValueError(
            f"Only {len(representatives)} fresh unique semantic stems remain; need {n}"
        )

    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for q in representatives:
        by_domain[q["domain"]].append(q)

    domain_caps = {d: len(rows) for d, rows in by_domain.items()}
    domain_quota = _apportion_with_caps(
        domain_caps, n, seed, "domain_apportion"
    )

    selected: list[dict[str, Any]] = []
    for domain in sorted(by_domain):
        quota = domain_quota[domain]
        if quota == 0:
            continue
        rows = by_domain[domain]
        by_diff: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for q in rows:
            by_diff[q["difficulty"]].append(q)
        diff_caps = {d: len(v) for d, v in by_diff.items()}
        diff_quota = _apportion_with_caps(
            diff_caps, quota, seed, f"difficulty_apportion:{domain}"
        )
        for diff in sorted(by_diff):
            pool = list(by_diff[diff])
            random.Random(
                stable_seed(seed, domain, diff, "heldout_pick")
            ).shuffle(pool)
            selected.extend(pool[:diff_quota[diff]])

    if len(selected) != n:
        raise AssertionError(f"Expected {n} selected items, got {len(selected)}")

    random.Random(stable_seed(seed, "heldout_final_order")).shuffle(selected)

    selected_ids = {q["id"] for q in selected}
    selected_stems = {canonical_stem(q["question"]) for q in selected}
    if selected_ids & exclude_ids:
        raise AssertionError("Held-out selection overlaps excluded source IDs")
    if selected_stems & exclude_stems:
        raise AssertionError("Held-out selection overlaps excluded stems")
    if len(selected_stems) != n:
        raise AssertionError("Held-out set contains duplicate semantic stems")

    out = []
    for i, q in enumerate(selected, 1):
        out.append({
            "task_id": f"T{i:03d}",
            "source_id": q["id"],
            "domain": q["domain"],
            "difficulty": q["difficulty"],
            "question": q["question"],
            "options": q["options"],
            "correct": q["correct"],
            "source_reasoning": q.get("reasoning"),
            "stem_sha256": sha256_text(canonical_stem(q["question"])),
        })
    return out
