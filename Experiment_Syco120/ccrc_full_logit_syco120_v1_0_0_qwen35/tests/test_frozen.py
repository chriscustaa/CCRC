from collections import Counter
from pathlib import Path

from harness.util import read_jsonl, sha256_file


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_hashes_and_sampling_cells():
    for line in (ROOT / "frozen" / "FROZEN_SHA256.txt").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        assert sha256_file(ROOT / "frozen" / name.strip()) == digest
    items = read_jsonl(ROOT / "frozen" / "items.jsonl")
    counts = Counter((x["confidence_stratum"], x["baseline_correct"]) for x in items)
    assert counts == Counter({(s, c): 20 for s in ("low", "mid", "high") for c in (True, False)})
    assert len({x["stem_sha256"] for x in items}) == 120
    for item in items:
        assert item["wrong_suggestion"] not in {item["baseline_answer"], item["correct_answer"]}
        assert set(item["baseline_logprobs"]) == set("ABCD")


def test_acceptance_slice():
    items = {x["question_id"]: x for x in read_jsonl(ROOT / "frozen" / "items.jsonl")}
    first = sorted(read_jsonl(ROOT / "frozen" / "call_plan.jsonl"), key=lambda x: x["call_index"])[:15]
    assert all(x["acceptance_cell"] for x in first)
    ids = {x["question_id"] for x in first}
    picked = [items[x] for x in ids]
    assert len(picked) == 6
    assert Counter((x["confidence_stratum"], x["baseline_correct"]) for x in picked) == Counter(
        {(s, c): 1 for s in ("low", "mid", "high") for c in (True, False)}
    )

