from harness.analysis import exact_one_sided_binomial, js_divergence, paired_binary, signed_test, softmax4


def test_exact_tests():
    assert abs(exact_one_sided_binomial(3, 0) - 0.125) < 1e-12
    assert signed_test([1, 2, 0, -1]) == {
        "positive": 2, "negative": 1, "ties": 1, "one_sided_exact_p": 0.5
    }
    paired = paired_binary([False, False, True, True], [True, False, True, False])
    assert paired["discordant_gains"] == 1
    assert paired["discordant_losses"] == 1


def test_distribution_helpers():
    p = softmax4({"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0})
    assert all(abs(p[x] - 0.25) < 1e-12 for x in "ABCD")
    assert abs(js_divergence(p, p)) < 1e-12

