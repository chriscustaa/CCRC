from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
from typing import Any, Iterable

from .util import canonical_json, sha256_text

DEFAULT_DATASET = "cais/mmlu"
DEFAULT_CONFIG = "all"
DEFAULT_SPLIT = "test"
# Parquet-era immutable MMLU revision. Script-era revisions are incompatible
# with Hugging Face datasets>=4, which no longer executes Hub dataset scripts.
DEFAULT_REVISION = "c30699e"


def _answer_letter(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid MMLU answer")
    if isinstance(value, int) and 0 <= value <= 3:
        return "ABCD"[value]
    text = str(value).strip().upper()
    if text in "ABCD" and len(text) == 1:
        return text
    if text in {"0", "1", "2", "3"}:
        return "ABCD"[int(text)]
    raise ValueError(f"Unsupported answer value: {value!r}")


def canonical_stem(question: str) -> str:
    return " ".join(str(question).casefold().split())


def _rank(seed: int, subject: str, source_index: int, question: str, choices: list[str]) -> str:
    # Deliberately excludes ground-truth answer from selection rank.
    payload = canonical_json({
        "seed": int(seed),
        "subject": subject,
        "source_index": int(source_index),
        "question": question,
        "choices": choices,
    })
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_stems: set[str] = set()
    for source_index, row in enumerate(rows):
        question = str(row.get("question", "")).strip()
        subject = str(row.get("subject", "")).strip()
        choices = [str(x) for x in list(row.get("choices") or [])]
        if not question or not subject or len(choices) != 4:
            continue
        stem = canonical_stem(question)
        if stem in seen_stems:
            continue
        seen_stems.add(stem)
        out.append({
            "source_index": source_index,
            "subject": subject,
            "question": question,
            "choices": choices,
            "correct_answer": _answer_letter(row.get("answer")),
            "semantic_stem_sha256": sha256_text(stem),
        })
    return out


def select_balanced(rows: Iterable[dict[str, Any]], *, n: int, seed: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    normalized = normalize_rows(rows)
    by_subject: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in normalized:
        by_subject[row["subject"]].append(row)
    subjects = sorted(by_subject)
    if not subjects:
        raise ValueError("No valid MMLU rows found")
    if n > len(normalized):
        raise ValueError(f"Requested n={n}, only {len(normalized)} unique valid rows")

    base, remainder = divmod(n, len(subjects))
    extra_order = sorted(subjects, key=lambda s: hashlib.sha256(f"{seed}|quota|{s}".encode()).hexdigest())
    extra = set(extra_order[:remainder])
    quotas = {s: base + (1 if s in extra else 0) for s in subjects}

    selected: list[dict[str, Any]] = []
    for subject in subjects:
        candidates = sorted(
            by_subject[subject],
            key=lambda r: _rank(seed, subject, r["source_index"], r["question"], r["choices"]),
        )
        quota = quotas[subject]
        if len(candidates) < quota:
            raise ValueError(f"Subject {subject!r} has {len(candidates)} rows, needs {quota}")
        selected.extend(candidates[:quota])

    selected = sorted(selected, key=lambda r: (r["subject"], r["source_index"]))
    for i, row in enumerate(selected):
        row["question_id"] = f"mmlu-{i:04d}"
        row["source_id"] = f"mmlu:{row['subject']}:{row['source_index']}"

    meta = {
        "normalized_n": len(normalized),
        "subject_count": len(subjects),
        "source_subject_counts": dict(sorted(Counter(r["subject"] for r in normalized).items())),
        "selected_subject_counts": dict(sorted(Counter(r["subject"] for r in selected).items())),
        "quotas": quotas,
    }
    return selected, meta


def load_mmlu(cfg: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ds_cfg = cfg.get("dataset") or {}
    name = str(ds_cfg.get("name", DEFAULT_DATASET))
    config = str(ds_cfg.get("config", DEFAULT_CONFIG))
    split = str(ds_cfg.get("split", DEFAULT_SPLIT))
    revision = str(ds_cfg.get("revision", DEFAULT_REVISION))
    n = int(ds_cfg.get("n", 1000))
    seed = int(cfg["seed"])

    import datasets
    from datasets import load_dataset

    try:
        dataset = load_dataset(name, config, split=split, revision=revision)
    except Exception as exc:
        if exc.__class__.__name__ == "DataFilesNotFoundError":
            raise RuntimeError(
                f"Dataset revision {revision!r} has no data files compatible with "
                f"datasets {datasets.__version__}. Use the frozen Parquet-era revision "
                f"{DEFAULT_REVISION!r}; do not downgrade the loader to rescue a script-era pin."
            ) from exc
        raise

    raw_rows = [dict(x) for x in dataset]
    selected, meta = select_balanced(raw_rows, n=n, seed=seed)
    meta.update({
        "name": name,
        "config": config,
        "split": split,
        "revision": revision,
        "datasets_version": datasets.__version__,
        "requested_n": n,
    })
    return selected, meta
