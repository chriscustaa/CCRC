import json
from pathlib import Path

from harness.design import STAGES, build_call_plan, stage_messages, validate_call_plan

ROOT = Path(__file__).resolve().parents[1]


def load_jsonl(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


def test_frozen_plan_is_exactly_100_by_5():
    items = load_jsonl(ROOT / "frozen" / "pilot_items.jsonl")
    plan = load_jsonl(ROOT / "frozen" / "call_plan.jsonl")
    assert len(items) == 100
    assert len(plan) == 500
    assert validate_call_plan(items, plan) == []
    assert build_call_plan(items, 2026082809) == plan


def test_prompts_are_stateless_and_stage_specific():
    item = load_jsonl(ROOT / "frozen" / "pilot_items.jsonl")[0]
    prompts = {stage: stage_messages(item, stage) for stage in STAGES}
    assert all(len(x) == 1 and x[0]["role"] == "user" for x in prompts.values())
    assert len({x[0]["content"] for x in prompts.values()}) == 5
    assert prompts["T0"][0]["content"].startswith(item["question"])
    assert all(item["question"] in x[0]["content"] for x in prompts.values())
