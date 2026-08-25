from harness.finalize import IMMUTABLE_TARGETS
def test_finalization_artifacts():
    assert "runs.jsonl" in IMMUTABLE_TARGETS
    assert "targets.jsonl" in IMMUTABLE_TARGETS
    assert "summary.json" in IMMUTABLE_TARGETS
