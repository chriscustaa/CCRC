from harness.summary import _m5_eval

def row(qid, cond, correct, target, scores):
    return {
        "question_id":qid,
        "condition":cond,
        "correct_answer":correct,
        "pressure_target":target,
        "parsed_first":max(scores, key=scores.get),
        "candidate_answer_logprobs":scores,
        "format_retry":None,
    }

def test_m5_can_correct_without_tuning():
    rows = {
        "q1": {
            "F": row("q1","F","A","B", {"A":-0.8,"B":-0.7,"C":-3,"D":-4}),
            "V": row("q1","V","A","B", {"A":-2.0,"B":-0.1,"C":-3,"D":-4}),
            "P": row("q1","P","A","B", {"A":-0.9,"B":-0.8,"C":-3,"D":-4}),
        }
    }
    got = _m5_eval(rows, "V", 1.0)
    assert got["f_argmax_accuracy"] == 0.0
    assert got["guided_argmax_accuracy"] == 1.0
    assert got["f_wrong_to_guided_correct_repairs"] == 1
