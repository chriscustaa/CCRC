from __future__ import annotations

from harness.dataset import normalize_question, select_balanced_unique
from harness.parsing import answer_candidate_logprobs, parse_mcq_letter
from harness.prompts import deterministic_wrong_letter, perturbation_message
from harness.runner import benchmark_output, benchmark_parsed


def fake_questions():
    out = []
    domains = ["d1", "d2", "d3", "d4"]
    diffs = ["easy", "medium", "hard"]
    idx = 0
    for d in domains:
        for diff in diffs:
            for j in range(5):
                idx += 1
                out.append({
                    "id": f"q{idx}",
                    "domain": d,
                    "difficulty": diff,
                    "question": f"{d} {diff} unique question {j}?",
                    "options": ["A) a", "B) b", "C) c", "D) d"],
                    "correct": "B",
                })
    return [normalize_question(q) for q in out]


def test_selection_is_deterministic_and_unique():
    qs = fake_questions()
    a = select_balanced_unique(qs, 12, 123)
    b = select_balanced_unique(qs, 12, 123)
    assert [x["source_id"] for x in a] == [x["source_id"] for x in b]
    assert len({x["question"] for x in a}) == 12


def test_parser():
    assert parse_mcq_letter("B") == "B"
    assert parse_mcq_letter("I choose A, but final answer: C") == "C"
    assert parse_mcq_letter("c") == "C"
    assert parse_mcq_letter("no answer") is None


def test_wrong_letter_and_prompt():
    assert deterministic_wrong_letter("A") == "B"
    assert deterministic_wrong_letter("C") == "A"
    msg = perturbation_message("wrong_suggest", 0, "C")
    assert "A" in msg


def test_candidate_logprobs():
    x = [{
        "token": " B",
        "logprob": -0.1,
        "top_logprobs": [
            {"token": " A", "logprob": -2.0},
            {"token": " B", "logprob": -0.1},
            {"token": " C", "logprob": -3.0},
        ],
    }]
    got = answer_candidate_logprobs(x)
    assert got["B"] == -0.1
    assert got["A"] == -2.0
    assert got["D"] is None


def test_benchmark_output_uses_retry_when_first_unparsed():
    record = {
        "raw_output": "I cannot decide",
        "parsed_first": None,
        "format_retry": {"raw_output": "C", "parsed": "C"},
    }
    assert benchmark_parsed(record) == "C"
    assert benchmark_output(record) == "C"


def test_benchmark_output_keeps_first_when_first_parsed():
    record = {
        "raw_output": "B",
        "parsed_first": "B",
        "format_retry": None,
    }
    assert benchmark_parsed(record) == "B"
    assert benchmark_output(record) == "B"
