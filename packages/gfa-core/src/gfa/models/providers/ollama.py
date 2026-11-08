"""Ollama model provider."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from gfa.models.base import (
    ChatRequest,
    ChatResponse,
    ModelCapabilities,
    ModelConfig,
    ProviderInfo,
)
from gfa.models.http import build_client, request_with_retry
from gfa.shared.errors import ConnectionFailedError, ProviderError


class OllamaProvider:
    info = ProviderInfo(id="ollama", name="Ollama", description="Local Ollama server.")

    def __init__(self, config: ModelConfig):
        self.config = config
        self._base = config.endpoint.rstrip("/")

    async def test_connection(self) -> dict[str, Any]:
        async with build_client(self.config.timeout) as client:
            try:
                resp = await request_with_retry(client, "GET", f"{self._base}/api/version", max_retries=1)
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "message": str(exc), "details": {}}
            if resp.status_code != 200:
                return {"ok": False, "message": f"HTTP {resp.status_code}", "details": {"body": resp.text[:500]}}
            try:
                data = resp.json()
            except ValueError:
                data = {}
            return {"ok": True, "message": "Connected to Ollama", "details": data}

    async def list_models(self) -> list[str]:
        async with build_client(self.config.timeout) as client:
            resp = await request_with_retry(client, "GET", f"{self._base}/api/tags", max_retries=1)
            if resp.status_code != 200:
                raise ConnectionFailedError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
            return [m.get("name") for m in data.get("models", []) if m.get("name")]

    async def chat(self, request: ChatRequest) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": False,
        }
        options: dict[str, Any] = {}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens
        if options:
            payload["options"] = options
        if request.response_format and request.response_format.get("type") == "json_object":
            payload["format"] = "json"

        async with build_client(self.config.request_timeout) as client:
            resp = await request_with_retry(client, "POST", f"{self._base}/api/chat", json=payload, max_retries=self.config.max_retries)
            if resp.status_code != 200:
                raise ProviderError(f"Ollama chat failed: HTTP {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
            msg = data.get("message", {}) or {}
            return ChatResponse(
                text=msg.get("content", "") or "",
                model=data.get("model", self.config.model),
                usage={
                    "prompt_tokens": data.get("prompt_eval_count"),
                    "completion_tokens": data.get("eval_count"),
                    "total_duration_ns": data.get("total_duration"),
                },
                raw=data,
                finish_reason=data.get("done_reason"),
            )

    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:  # pragma: no cover - optional
        payload = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": True,
        }
        async with build_client(self.config.request_timeout) as client, client.stream("POST", f"{self._base}/api/chat", json=payload) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        continue
                    chunk = (obj.get("message") or {}).get("content")
                    if chunk:
                        yield chunk

    async def detect_capabilities(self) -> ModelCapabilities:
        caps = ModelCapabilities()
        # Try /api/show for details
        try:
            async with build_client(self.config.timeout) as client:
                resp = await request_with_retry(client, "POST", f"{self._base}/api/show", json={"name": self.config.model}, max_retries=1)
                if resp.status_code == 200:
                    data = resp.json()
                    # Heuristic: if model name contains vision-ish hints
                    details = str(data).lower()
                    if "vision" in details or "llava" in self.config.model.lower() or "bakllava" in self.config.model.lower():
                        caps.image_input = True
                    caps.context_window = data.get("model_info", {}).get("context_length") if isinstance(data.get("model_info"), dict) else None
        except Exception:  # noqa: BLE001
            pass
        return caps