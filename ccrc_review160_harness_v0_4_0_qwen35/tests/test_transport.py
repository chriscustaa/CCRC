from harness.transport_check import _compact_result

def test_compact_result_reasoning_and_parse():
    result = {
        "text":"A",
        "token_logprobs":[{"token":"A","logprob":0.0}],
        "usage":{},
        "reasoning_tokens":0,
        "reasoning_content_present":False,
        "reasoning_detected":False,
        "request_meta":{},
        "meta":{"model":"m"},
    }
    got = _compact_result(result,[{"role":"user","content":"x"}])
    assert got["parsed"] == "A"
    assert got["reasoning_detected"] is False
