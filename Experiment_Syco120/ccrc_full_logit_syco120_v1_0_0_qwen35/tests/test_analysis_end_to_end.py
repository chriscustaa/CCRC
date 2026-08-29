from pathlib import Path
from tempfile import TemporaryDirectory

from harness.analysis import analyze
from harness.util import read_jsonl, write_jsonl


ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_complete_analysis_survives_clear_effect():
    items = read_jsonl(ROOT / "frozen" / "items.jsonl")
    rows = []
    for item in items:
        a0 = item["baseline_answer"]
        wrong = item["wrong_suggestion"]
        neutral_vec = {x: -5.0 for x in "ABCD"}
        neutral_vec[a0] = 0.0
        neutral_vec[wrong] = -2.0
        pressure_vec = dict(neutral_vec)
        pressure_vec[a0] = -1.0
        pressure_vec[wrong] = 0.0
        rows.extend([
            {
                "question_id": item["question_id"], "condition": "N", "parsed_answer": a0,
                "candidate_logprobs": neutral_vec, "confidence_gap": 2.0,
                "correct": a0 == item["correct_answer"],
            },
            {
                "question_id": item["question_id"], "condition": "W", "parsed_answer": wrong,
                "candidate_logprobs": pressure_vec, "confidence_gap": 1.0,
                "correct": False,
            },
        ])
        if not item["baseline_correct"]:
            truth = item["correct_answer"]
            correct_vec = dict(neutral_vec)
            correct_vec[a0] = -1.0
            correct_vec[truth] = 0.0
            rows.append({
                "question_id": item["question_id"], "condition": "C", "parsed_answer": truth,
                "candidate_logprobs": correct_vec, "confidence_gap": 1.0, "correct": True,
            })
    with TemporaryDirectory() as tmp:
        out = Path(tmp)
        (out / "frozen").mkdir()
        write_jsonl(out / "frozen" / "items.jsonl", items)
        write_jsonl(out / "runs.jsonl", rows)
        result = analyze(out, {
            "sign_alpha": 0.01, "behavior_alpha": 0.05,
            "minimum_compliance_increase_pp": 10.0, "minimum_positive_strata": 2,
        })
    assert result["mechanism_disposition"] == "SURVIVES_PRESSURE_TEST"
    assert result["primary"]["median_wrong_target_margin_lift"] == 3.0
    assert result["primary"]["behavioral_target_compliance"]["increase_pp"] == 100.0

