from harness.transport_check import _compact_result


def test_transport_compact_result_preserves_request_meta():
    messages = [{"role": "user", "content": "x"}]
    result = {
        "text": "B",
        "token_logprobs": [{"token": " B", "logprob": -0.1, "top_logprobs": []}],
        "usage": {"input_tokens": 1},
        "latency_s": 0.1,
        "request_meta": {"endpoint": "/v1/responses", "seed_sent": True},
        "meta": {"model": "x"},
    }
    got = _compact_result(result, messages)
    assert got["parsed"] == "B"
    assert got["has_token_logprobs"] is True
    assert got["transport_request_meta"]["seed_sent"] is True
