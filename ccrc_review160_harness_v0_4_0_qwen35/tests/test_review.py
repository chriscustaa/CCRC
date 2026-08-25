from harness.prompts import CONDITIONS, followup_messages, format_question_prompt, prompt_audit
from harness.targets import assign_balanced_targets

def item(i=1, correct="A"):
    return {
        "task_id": f"T{i:03d}",
        "source_id": f"q{i}",
        "domain": "d",
        "difficulty": "easy",
        "question": "Which?",
        "options": {"A":"a","B":"b","C":"c","D":"d"},
        "correct": correct,
    }

def test_shared_model_baseline_prefix():
    q = format_question_prompt("Which?", item()["options"])
    for cond in CONDITIONS:
        msgs = followup_messages(q, "C", cond, "B")
        assert msgs[1] == {"role":"assistant","content":"C"}
        assert len(msgs) == 3

def test_constructive_conditions_are_non_directional():
    rows = {r["condition"]: r for r in prompt_audit()}
    for cond in ["R0","R1","R2","R3"]:
        text = rows[cond]["text"].lower()
        assert "option b" not in text
        assert "your answer is wrong" not in text
        assert rows[cond]["contains_wrong_claim"] is False
    assert rows["V"]["contains_wrong_claim"] is True

def test_targets_are_wrong_and_balanced():
    items = [item(i, "ABCD"[(i-1)%4]) for i in range(1, 161)]
    ts = assign_balanced_targets(items, 20260823)
    counts = {x:0 for x in "ABCD"}
    by = {x["question_id"]:x for x in ts}
    for x in items:
        t = by[x["source_id"]]["pressure_target"]
        assert t != x["correct"]
        counts[t] += 1
    assert max(counts.values()) - min(counts.values()) <= 1
