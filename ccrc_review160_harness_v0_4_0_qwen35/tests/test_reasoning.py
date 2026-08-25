from harness.lmstudio import _reasoning_telemetry

def test_no_reasoning():
    x = {"usage":{"output_tokens_details":{"reasoning_tokens":0}}, "output":[]}
    got = _reasoning_telemetry(x)
    assert got["reasoning_detected"] is False

def test_reasoning_tokens_detected():
    x = {"usage":{"output_tokens_details":{"reasoning_tokens":7}}, "output":[]}
    got = _reasoning_telemetry(x)
    assert got["reasoning_detected"] is True
    assert got["reasoning_tokens"] == 7

def test_reasoning_item_detected():
    x = {"usage":{"output_tokens_details":{"reasoning_tokens":0}}, "output":[{"type":"reasoning"}]}
    got = _reasoning_telemetry(x)
    assert got["reasoning_detected"] is True
