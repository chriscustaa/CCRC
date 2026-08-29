from harness.design import build_call_plan, condition_messages, validate_call_plan
from harness.util import read_jsonl
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_plan_structure():
    items = read_jsonl(ROOT / "frozen" / "items.jsonl")
    plan = read_jsonl(ROOT / "frozen" / "call_plan.jsonl")
    assert validate_call_plan(items, plan) == []
    assert len(items) == 120
    assert len(plan) == 300
    assert sum(x["condition"] == "N" for x in plan) == 120
    assert sum(x["condition"] == "W" for x in plan) == 120
    assert sum(x["condition"] == "C" for x in plan) == 60


def test_message_transcript_and_target_identity():
    item = next(x for x in read_jsonl(ROOT / "frozen" / "items.jsonl") if not x["baseline_correct"])
    neutral = condition_messages(item, "N")
    wrong = condition_messages(item, "W")
    correct = condition_messages(item, "C")
    assert [x["role"] for x in neutral] == ["user", "assistant", "user"]
    assert neutral[1]["content"] == item["baseline_answer"]
    assert item["wrong_suggestion"] in wrong[-1]["content"]
    assert item["correct_answer"] in correct[-1]["content"]

