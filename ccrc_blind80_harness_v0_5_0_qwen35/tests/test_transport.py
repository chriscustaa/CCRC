from harness.transport_check import _compact

def test_compact():
    result={
        "text":"A",
        "token_logprobs":[{"token":"A","logprob":0.0}],
        "reasoning_detected":False,
        "usage":{},
        "request_meta":{},
        "meta":{"model":"m"},
    }
    got=_compact(result,[{"role":"user","content":"x"}])
    assert got["parsed"]=="A"
    assert got["reasoning_detected"] is False
