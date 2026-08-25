from harness.model_identity import (
    _profile_mismatches,
    stable_model_snapshot,
    snapshot_sha256,
)

EXPECTED = {
    "architecture": "qwen2",
    "quantization": "Q4_K_M",
    "params_string": "7B",
    "format": "gguf",
    "display_name_contains": ["Qwen2.5", "7B", "Instruct"],
    "display_name_forbids": ["VL", "Coder", "Math"],
    "vision": False,
    "require_exactly_one_loaded_instance": True,
}

def good_model():
    return {
        "key": "qwen/qwen2.5-7b-instruct",
        "display_name": "Qwen2.5 7B Instruct",
        "architecture": "qwen2",
        "quantization": {"name": "Q4_K_M", "bits_per_weight": 4},
        "size_bytes": 4680000000,
        "params_string": "7B",
        "loaded_instances": [{"id": "qwen/qwen2.5-7b-instruct", "config": {"context_length": 32768}}],
        "max_context_length": 131072,
        "format": "gguf",
        "capabilities": {"vision": False},
        "selected_variant": "qwen/qwen2.5-7b-instruct@q4_k_m",
    }

def test_good_model_matches():
    assert _profile_mismatches(good_model(), EXPECTED) == []

def test_vl_model_rejected():
    m = good_model()
    m["display_name"] = "Qwen2.5 VL 7B"
    m["architecture"] = "qwen2vl"
    m["capabilities"]["vision"] = True
    mismatches = _profile_mismatches(m, EXPECTED)
    assert any("architecture" in x for x in mismatches)
    assert any("forbidden" in x or "missing required" in x for x in mismatches)
    assert any("vision" in x for x in mismatches)

def test_wrong_quant_rejected():
    m = good_model()
    m["quantization"]["name"] = "Q5_K_M"
    assert any("quantization" in x for x in _profile_mismatches(m, EXPECTED))

def test_unloaded_rejected():
    m = good_model()
    m["loaded_instances"] = []
    assert any("loaded_instances" in x for x in _profile_mismatches(m, EXPECTED))

def test_duplicate_loaded_instances_rejected():
    m = good_model()
    m["loaded_instances"].append({"id": "second", "config": {"context_length": 32768}})
    assert any("exactly 1" in x for x in _profile_mismatches(m, EXPECTED))

def test_snapshot_hash_changes_with_runtime_config():
    a = stable_model_snapshot(good_model())
    m = good_model()
    m["loaded_instances"][0]["config"]["context_length"] = 65536
    b = stable_model_snapshot(m)
    assert snapshot_sha256(a) != snapshot_sha256(b)
