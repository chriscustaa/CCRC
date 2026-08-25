from harness.model_identity import (
    _profile_mismatches,
    stable_model_snapshot,
    snapshot_sha256,
)

EXPECTED = {
    "architecture": "qwen35",
    "quantization": "Q4_K_M",
    "params_string": "9B",
    "format": "gguf",
    "display_name_contains": ["Qwen3.5", "9B"],
    "display_name_forbids": ["Coder", "Math", "Uncensored"],
    "vision": True,
    "reasoning_capability_required": True,
    "require_exactly_one_loaded_instance": True,
}

def good_model():
    return {
        "key": "qwen/qwen3.5-9b",
        "display_name": "Qwen3.5 9B",
        "architecture": "qwen35",
        "quantization": {"name": "Q4_K_M", "bits_per_weight": 4},
        "size_bytes": 6548926907,
        "params_string": "9B",
        "loaded_instances": [{"id": "qwen/qwen3.5-9b", "config": {"context_length": 32768}}],
        "max_context_length": 262144,
        "format": "gguf",
        "capabilities": {
            "vision": True,
            "trained_for_tool_use": True,
            "reasoning": {"allowed_options": ["off", "on"], "default": "on"},
        },
        "selected_variant": "qwen/qwen3.5-9b@q4_k_m",
    }

def test_good_model_matches():
    assert _profile_mismatches(good_model(), EXPECTED) == []

def test_qwen25_rejected():
    m = good_model()
    m["display_name"] = "Qwen2.5 7B Instruct"
    m["architecture"] = "qwen2"
    m["params_string"] = "7B"
    mismatches = _profile_mismatches(m, EXPECTED)
    assert any("architecture" in x for x in mismatches)
    assert any("params_string" in x for x in mismatches)

def test_wrong_quant_rejected():
    m = good_model()
    m["quantization"]["name"] = "Q5_K_M"
    assert any("quantization" in x for x in _profile_mismatches(m, EXPECTED))

def test_reasoning_control_required():
    m = good_model()
    m["capabilities"].pop("reasoning")
    assert any("reasoning capability" in x for x in _profile_mismatches(m, EXPECTED))

def test_unloaded_rejected():
    m = good_model()
    m["loaded_instances"] = []
    assert any("loaded_instances" in x for x in _profile_mismatches(m, EXPECTED))

def test_snapshot_hash_changes_with_runtime_config():
    a = stable_model_snapshot(good_model())
    m = good_model()
    m["loaded_instances"][0]["config"]["context_length"] = 65536
    b = stable_model_snapshot(m)
    assert snapshot_sha256(a) != snapshot_sha256(b)
