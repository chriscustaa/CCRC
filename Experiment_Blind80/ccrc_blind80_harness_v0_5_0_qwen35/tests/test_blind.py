from harness.prompts import (
    blind_messages, format_question_prompt, visible_self_messages, CORE_REDERIVE
)

def qprompt():
    return format_question_prompt(
        "Which?",
        {"A":"a","B":"b","C":"c","D":"d"}
    )

def test_S0_contains_prior_answer():
    msgs = visible_self_messages(qprompt(), "C")
    assert msgs[1] == {"role":"assistant","content":"C"}
    assert msgs[2]["content"] == CORE_REDERIVE

def test_D0_hides_prior_answer_and_uses_same_core_instruction():
    msgs = blind_messages(qprompt(), "D0")
    assert len(msgs) == 1
    assert all(m["role"] != "assistant" for m in msgs)
    assert CORE_REDERIVE in msgs[0]["content"]
    assert "ASSISTANT" not in msgs[0]["content"]

def test_other_blind_branches_hide_prior_answer():
    for cond in ["D1","D2","D3","DP"]:
        msgs = blind_messages(qprompt(), cond)
        assert all(m["role"] != "assistant" for m in msgs)
