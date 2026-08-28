from __future__ import annotations

from typing import Any

from .lmstudio import LMStudioClient
from .util import canonical_json, sha256_text

DEFAULT_EXPECTED_MODEL: dict[str, Any] = {
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


class ModelIdentityError(RuntimeError):
    def __init__(self, message: str, report: dict[str, Any]):
        super().__init__(message)
        self.report = report


def expected_model_from_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    expected = dict(DEFAULT_EXPECTED_MODEL)
    user = cfg.get("expected_model")
    if isinstance(user, dict):
        expected.update(user)
    return expected


def _native_models(client: LMStudioClient) -> list[dict[str, Any]]:
    payload = client.models_native_v1()
    models = payload.get("models") or []
    return [m for m in models if isinstance(m, dict)]


def _openai_models(client: LMStudioClient) -> list[dict[str, Any]]:
    payload = client.models_openai()
    data = payload.get("data") or []
    return [m for m in data if isinstance(m, dict)]


def _vision_value(model: dict[str, Any]) -> bool:
    caps = model.get("capabilities") or {}
    return bool(caps.get("vision", False))


def _profile_mismatches(model: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    mismatches: list[str] = []

    exact_fields = {
        "architecture": model.get("architecture"),
        "params_string": model.get("params_string"),
        "format": model.get("format"),
    }
    for field, observed in exact_fields.items():
        wanted = expected.get(field)
        if wanted is not None and str(observed).lower() != str(wanted).lower():
            mismatches.append(f"{field}: expected {wanted!r}, observed {observed!r}")

    q = model.get("quantization") or {}
    observed_quant = q.get("name")
    wanted_quant = expected.get("quantization")
    if wanted_quant is not None and str(observed_quant).lower() != str(wanted_quant).lower():
        mismatches.append(
            f"quantization: expected {wanted_quant!r}, observed {observed_quant!r}"
        )

    display = str(model.get("display_name") or "")
    for needle in expected.get("display_name_contains") or []:
        if str(needle).lower() not in display.lower():
            mismatches.append(
                f"display_name missing required text {needle!r}: observed {display!r}"
            )
    for needle in expected.get("display_name_forbids") or []:
        if str(needle).lower() in display.lower():
            mismatches.append(
                f"display_name contains forbidden text {needle!r}: observed {display!r}"
            )

    wanted_vision = expected.get("vision")
    if wanted_vision is not None:
        observed_vision = _vision_value(model)
        if observed_vision is not bool(wanted_vision):
            mismatches.append(
                f"vision capability: expected {bool(wanted_vision)!r}, observed {observed_vision!r}"
            )

    if expected.get("reasoning_capability_required", False):
        caps = model.get("capabilities") or {}
        reasoning = caps.get("reasoning")
        if not isinstance(reasoning, dict):
            mismatches.append("reasoning capability: expected reasoning metadata, observed none")
        else:
            allowed = reasoning.get("allowed_options") or []
            lowered = {str(x).lower() for x in allowed}
            if not ({"off", "on"} <= lowered or "off" in lowered):
                mismatches.append(
                    f"reasoning capability: expected an OFF-capable reasoning control, observed {allowed!r}"
                )

    loaded = model.get("loaded_instances") or []
    if expected.get("require_exactly_one_loaded_instance", True):
        if len(loaded) != 1:
            mismatches.append(
                f"loaded_instances: expected exactly 1, observed {len(loaded)}"
            )
    elif len(loaded) < 1:
        mismatches.append("loaded_instances: model is not loaded")

    return mismatches


def stable_model_snapshot(model: dict[str, Any]) -> dict[str, Any]:
    loaded = model.get("loaded_instances") or []
    loaded_cfg = None
    if len(loaded) == 1 and isinstance(loaded[0], dict):
        loaded_cfg = loaded[0].get("config")

    return {
        "key": model.get("key"),
        "display_name": model.get("display_name"),
        "architecture": model.get("architecture"),
        "quantization": model.get("quantization"),
        "size_bytes": model.get("size_bytes"),
        "params_string": model.get("params_string"),
        "max_context_length": model.get("max_context_length"),
        "format": model.get("format"),
        "capabilities": model.get("capabilities"),
        "selected_variant": model.get("selected_variant"),
        "loaded_instance_count": len(loaded),
        "loaded_instance_config": loaded_cfg,
    }


def snapshot_sha256(snapshot: dict[str, Any]) -> str:
    return sha256_text(canonical_json(snapshot))


def build_identity_report(
    client: LMStudioClient,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    configured = cfg.get("model_id")
    expected = expected_model_from_cfg(cfg)
    openai = _openai_models(client)
    native = _native_models(client)

    openai_ids = [m.get("id") for m in openai if m.get("id")]
    native_keys = [m.get("key") for m in native if m.get("key")]

    matching_loaded_candidates = []
    for m in native:
        if not _profile_mismatches(m, expected):
            matching_loaded_candidates.append({
                "key": m.get("key"),
                "display_name": m.get("display_name"),
                "selected_variant": m.get("selected_variant"),
                "architecture": m.get("architecture"),
                "quantization": (m.get("quantization") or {}).get("name"),
                "params_string": m.get("params_string"),
            })

    exact_native = next(
        (m for m in native if configured is not None and m.get("key") == configured),
        None,
    )

    blocking: list[str] = []
    if not configured:
        blocking.append(
            "model_id is null. Set it to the exact loaded LM Studio model key before inference."
        )
    elif configured not in openai_ids:
        blocking.append(
            f"configured model_id {configured!r} does not exactly exist in /v1/models"
        )
    if configured and configured not in native_keys:
        blocking.append(
            f"configured model_id {configured!r} does not exactly exist in /api/v1/models"
        )

    profile_mismatches: list[str] = []
    snapshot = None
    snapshot_hash = None
    if exact_native is not None:
        profile_mismatches = _profile_mismatches(exact_native, expected)
        blocking.extend(profile_mismatches)
        snapshot = stable_model_snapshot(exact_native)
        snapshot_hash = snapshot_sha256(snapshot)

    report = {
        "configured_model_id": configured,
        "expected_model": expected,
        "openai_exact_id_present": bool(configured and configured in openai_ids),
        "native_exact_key_present": bool(configured and configured in native_keys),
        "matching_loaded_candidates": matching_loaded_candidates,
        "profile_mismatches": profile_mismatches,
        "model_snapshot": snapshot,
        "model_snapshot_sha256": snapshot_hash,
        "status": "PASS" if not blocking else "BLOCK",
        "blocking_reasons": blocking,
    }
    return report


def resolve_model_strict(
    client: LMStudioClient,
    cfg: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    report = build_identity_report(client, cfg)
    if report["status"] != "PASS":
        candidates = report.get("matching_loaded_candidates") or []
        hint = ""
        if candidates:
            hint = " Matching loaded candidate(s): " + ", ".join(
                str(x.get("key")) for x in candidates
            )
        raise ModelIdentityError(
            "Strict model identity validation failed: "
            + "; ".join(report["blocking_reasons"])
            + hint,
            report,
        )
    return str(report["configured_model_id"]), report
