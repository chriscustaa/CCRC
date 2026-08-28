from collections import Counter
from harness.dataset import select_balanced


def test_selection_balanced_and_does_not_need_answers_for_rank():
    rows = []
    for s in ("s1", "s2", "s3"):
        for i in range(10):
            rows.append({"question": f"{s} q{i}", "subject": s, "choices": ["a", "b", "c", "d"], "answer": i % 4})
    selected, meta = select_balanced(rows, n=8, seed=42)
    counts = Counter(x["subject"] for x in selected)
    assert sorted(counts.values()) == [2, 3, 3]
    assert len({x["semantic_stem_sha256"] for x in selected}) == 8
