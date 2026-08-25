from harness.policy import answer_gap, majority3, policy_decision


def test_gap_requires_complete_abcd():
    assert abs(answer_gap({"A": -0.1, "B": -0.3, "C": -1.0, "D": -2.0}) - 0.2) < 1e-12
    assert answer_gap({"A": -0.1, "B": -0.3, "C": None, "D": -2.0}) is None


def test_high_margin_bypasses_blind():
    out = policy_decision(baseline="A", blind="B", v1="B", v2="B", gap=0.8, theta=0.2)
    assert out["answer"] == "A" and not out["used_d"]


def test_low_margin_consensus_and_verifier():
    assert policy_decision(baseline="A", blind="A", v1=None, v2=None, gap=0.1, theta=0.2)["answer"] == "A"
    out = policy_decision(baseline="A", blind="B", v1="B", v2="C", gap=0.1, theta=0.2)
    assert out["answer"] == "B" and out["used_v"]
    assert majority3("A", "B", "C") is None
