from harness.analysis import _balanced_schedule_distribution, majority3


def test_majority_three_never_uses_eight_votes():
    assert majority3(["A", "A", "B"]) == "A"
    assert majority3(["A", "B", "C"]) is None


def test_exact_balanced_schedule_enumeration():
    # Four items, every ordered R1/R2 slot pair admissible, every item net +1.
    pairs = [[(a, b, 1) for a in range(4) for b in range(4)] for _ in range(4)]
    result = _balanced_schedule_distribution(pairs)
    assert result["schedule_count"] == 24 * 24
    assert result["net_distribution"] == {"4": 24 * 24}
    assert result["positive_schedule_fraction"] == 1.0
    assert result["exact_expected_net"] == 4.0


def test_zero_is_nonpositive():
    pairs = [[(a, b, 0) for a in range(4) for b in range(4)] for _ in range(4)]
    result = _balanced_schedule_distribution(pairs)
    assert result["positive_schedule_fraction"] == 0.0

