from __future__ import annotations

import json
import time
import os
from dataclasses import dataclass
from typing import Any

import requests


class LMStudioError(RuntimeError):
    pass


def _reasoning_telemetry(data: dict[str, Any]) -> dict[str, Any]:
    usage = data.get("usage") or {}
    details = (
        usage.get("output_tokens_details")
        or usage.get("completion_tokens_details")
        or {}
    )
    rt = details.get("reasoning_tokens")
    try:
        reasoning_tokens = int(rt or 0)
    except (TypeError, ValueError):
        reasoning_tokens = 0

    reasoning_content_present = False
    # Chat-style reasoning_content.
    for choice in data.get("choices") or []:
        msg = choice.get("message") if isinstance(choice, dict) else None
        if isinstance(msg, dict) and msg.get("reasoning_content"):
            reasoning_content_present = True
    # Responses-style reasoning output item.
    for item in data.get("output") or []:
        if isinstance(item, dict) and str(item.get("type", "")).lower() in {
            "reasoning", "reasoning_content"
        }:
            reasoning_content_present = True

    return {
        "reasoning_tokens": reasoning_tokens,
        "reasoning_content_present": reasoning_content_present,
        "reasoning_detected": bool(reasoning_tokens > 0 or reasoning_content_present),
    }


@dataclass
class LMStudioClient:
    base_url: str
    timeout_s: float = 120.0
    api_token: str | None = None

    def __post_init__(self) -> None:
        if self.api_token is None:
            self.api_token = os.getenv("LM_API_TOKEN")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    def _url(self, path: str) -> str:
        return self.base_url.rstrip("/") + path

    def _get_json(self, path: str) -> dict[str, Any]:
        r = requests.get(
            self._url(path),
            headers=self._headers(),
            timeout=self.timeout_s,
        )
        if r.status_code != 200:
            raise LMStudioError(f"GET {path} -> HTTP {r.status_code}: {r.text[:500]}")
        return r.json()

    def models_openai(self) -> dict[str, Any]:
        return self._get_json("/v1/models")

    def models_native_v1(self) -> dict[str, Any]:
        return self._get_json("/api/v1/models")

    def models_native_v0(self) -> dict[str, Any]:
        return self._get_json("/api/v0/models")

    def _post(self, path: str, payload: dict[str, Any]) -> tuple[dict[str, Any], float]:
        t0 = time.perf_counter()
        r = requests.post(
            self._url(path),
            json=payload,
            headers=self._headers(),
            timeout=self.timeout_s,
        )
        latency = time.perf_counter() - t0
        if r.status_code != 200:
            raise LMStudioError(
                f"POST {path} -> HTTP {r.status_code}: {r.text[:1000]}"
            )
        return r.json(), latency

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        top_p: float,
        max_tokens: int,
        seed: int | None,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stream": False,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
        }
        if seed is not None:
            payload["seed"] = seed
        data, latency = self._post("/v1/chat/completions", payload)
        text = ""
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except Exception as exc:
            raise LMStudioError(f"Unexpected chat response: {json.dumps(data)[:1200]}") from exc
        telemetry = _reasoning_telemetry(data)
        return {
            "text": text,
            "token_logprobs": None,
            **telemetry,
            "usage": data.get("usage"),
            "latency_s": latency,
            "raw_response": data,
            "request_meta": {
                "endpoint": "/v1/chat/completions",
                "seed_requested": seed,
                "seed_sent": seed is not None,
                "stateful_continuation_used": False,
                "logit_bias_used": False,
                "presence_penalty": presence_penalty,
                "frequency_penalty": frequency_penalty,
            },
            "meta": {
                "id": data.get("id"),
                "model": data.get("model"),
                "system_fingerprint": data.get("system_fingerprint"),
                "finish_reason": (data.get("choices") or [{}])[0].get("finish_reason"),
            },
        }

    @staticmethod
    def _extract_response_text_and_logprobs(data: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
        texts: list[str] = []
        logprobs: list[dict[str, Any]] = []
        for item in data.get("output") or []:
            if not isinstance(item, dict):
                continue
            for part in item.get("content") or []:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "output_text":
                    texts.append(part.get("text") or "")
                    for lp in part.get("logprobs") or []:
                        if isinstance(lp, dict):
                            logprobs.append(lp)
        # Some implementations may expose output_text directly.
        if not texts and isinstance(data.get("output_text"), str):
            texts.append(data["output_text"])
        return "".join(texts), logprobs

    def responses(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        top_p: float,
        max_tokens: int,
        seed: int | None,
        top_logprobs: int,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "input": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": max_tokens,
            "include": ["message.output_text.logprobs"],
            "top_logprobs": top_logprobs,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
        }
        # Seed is not guaranteed by the Responses spec. Try it only if supplied.
        seed_sent = seed is not None
        seed_rejected = False
        if seed is not None:
            payload["seed"] = seed
        try:
            data, latency = self._post("/v1/responses", payload)
        except LMStudioError as exc:
            # The Open Responses path may not implement `seed` on every LM Studio/runtime
            # combination. At temperature=0 we can still run, but the loss of an explicit
            # seed is recorded as experimental metadata rather than hidden.
            if seed is not None and "seed" in str(exc).lower():
                payload.pop("seed", None)
                seed_sent = False
                seed_rejected = True
                data, latency = self._post("/v1/responses", payload)
            else:
                raise
        text, logprobs = self._extract_response_text_and_logprobs(data)
        if text == "" and not data.get("output"):
            raise LMStudioError(f"Unexpected responses payload: {json.dumps(data)[:1200]}")
        telemetry = _reasoning_telemetry(data)
        return {
            "text": text,
            "token_logprobs": logprobs or None,
            **telemetry,
            "usage": data.get("usage"),
            "latency_s": latency,
            "raw_response": data,
            "request_meta": {
                "endpoint": "/v1/responses",
                "seed_requested": seed,
                "seed_sent": seed_sent,
                "seed_rejected": seed_rejected,
                "stateful_continuation_used": False,
                "previous_response_id": None,
                "logit_bias_used": False,
                "logprobs_requested": True,
                "top_logprobs_requested": top_logprobs,
                "presence_penalty": presence_penalty,
                "frequency_penalty": frequency_penalty,
            },
            "meta": {
                "id": data.get("id"),
                "model": data.get("model"),
                "status": data.get("status"),
            },
        }

    def generate(
        self,
        transport: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if transport == "chat":
            kwargs.pop("top_logprobs", None)
            return self.chat(**kwargs)
        if transport == "responses":
            return self.responses(**kwargs)
        raise ValueError(f"Unknown transport: {transport}")
