from harness.analysis import _policy_metrics, one_sided_exact_repairs_gt_harms


def fake_item(t0, late, truth, centered=1.0):
    stages = {
        "T0": {"parsed_answer": t0, "correct": t0 == truth},
        "T1": {"parsed_answer": t0, "correct": t0 == truth},
        "T2": {"parsed_answer": late, "correct": late == truth},
        "T3": {"parsed_answer": late, "correct": late == truth},
        "T4": {"parsed_answer": late, "correct": late == truth},
    }
    return {
        "correct_answer": truth,
        "stages": stages,
        "control_centered_gap_change": {"T0": 0.0, "T1": 0.0, "T2": centered, "T3": centered, "T4": centered},
    }


def test_frozen_policy_repairs_and_harms():
    metrics = _policy_metrics([
        fake_item("A", "B", "B"),
        fake_item("A", "B", "A"),
        fake_item("A", "B", "B", centered=-1.0),
    ])
    assert metrics["switches"] == 2
    assert metrics["repairs"] == 1
    assert metrics["harms"] == 1
    assert metrics["net"] == 0


def test_exact_one_sided_sign_test():
    assert one_sided_exact_repairs_gt_harms(0, 0) == 1.0
    assert one_sided_exact_repairs_gt_harms(3, 0) == 0.125
