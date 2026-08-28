from harness.finalize import IMMUTABLE_TARGETS

def test_finalization_artifacts():
    assert "runs.jsonl" in IMMUTABLE_TARGETS
    assert "excluded_items.jsonl" in IMMUTABLE_TARGETS
    assert "prompt_audit.json" in IMMUTABLE_TARGETS
    assert "summary.json" in IMMUTABLE_TARGETS
