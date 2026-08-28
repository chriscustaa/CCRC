import json
from pathlib import Path

from harness.design import LETTERS, VERIFIER_PREFIX, build_call_plan, validate_call_plan, verifier_messages

ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_frozen_plan_has_568_balanced_cells():
    items = load_jsonl(ROOT / "frozen" / "replay_items.jsonl")
    plan = load_jsonl(ROOT / "frozen" / "call_plan.jsonl")
    assert len(items) == 71
    assert len(plan) == 568
    assert validate_call_plan(items, plan) == []


def test_design_rebuild_is_byte_equivalent_in_content():
    items = load_jsonl(ROOT / "frozen" / "replay_items.jsonl")
    plan = load_jsonl(ROOT / "frozen" / "call_plan.jsonl")
    assert build_call_plan(items, 2026082607) == plan


def test_verifier_wording_is_identical_across_streams():
    items = load_jsonl(ROOT / "frozen" / "replay_items.jsonl")
    plan = load_jsonl(ROOT / "frozen" / "call_plan.jsonl")
    item = items[0]
    rows = [x for x in plan if x["question_id"] == item["question_id"] and x["placement"] == "P0"]
    assert len(rows) == 2
    assert verifier_messages(item, rows[0]["option_order"]) == verifier_messages(item, rows[1]["option_order"])
    assert verifier_messages(item, rows[0]["option_order"])[0]["content"].startswith(VERIFIER_PREFIX)
    for stream in ("R1", "R2"):
        slots = sorted(x["correct_display_slot"] for x in plan if x["question_id"] == item["question_id"] and x["replicate_stream"] == stream)
        assert slots == list(LETTERS)

