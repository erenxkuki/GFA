"""OpenAI-compatible model provider (covers OpenAI, LM Studio, and custom endpoints)."""

from __future__ import annotations

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


class OpenAICompatibleProvider:
    info = ProviderInfo(id="openai-compatible", name="OpenAI-Compatible",
                        description="OpenAI chat/completions compatible endpoint.")

    def __init__(self, config: ModelConfig):
        self.config = config
        self._base = config.endpoint.rstrip("/")
        if not self._base.endswith("/v1") and "/v1" not in self._base:
            # Most compatible servers expose /v1; keep user-provided base as-is otherwise.
            pass

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _url(self, path: str) -> str:
        base = self._base
        if base.endswith("/"):
            base = base[:-1]
        if not base.endswith("/v1") and "/v1/" not in base + "/" and not base.rstrip("/").endswith("v1"):
            # append /v1 for bare host roots
            base = base + "/v1"
        return f"{base}{path}"

    async def test_connection(self) -> dict[str, Any]:
        async with build_client(self.config.timeout, headers=self._headers()) as client:
            try:
                resp = await request_with_retry(client, "GET", self._url("/models"), max_retries=1)
            except Exception as exc:  # noqa: BLE001
                return {"ok": False, "message": str(exc), "details": {}}
            if resp.status_code == 404:
                # Some servers (LM Studio) may need /v1/models; if 404 try root
                return {"ok": False, "message": f"HTTP {resp.status_code}", "details": {"body": resp.text[:500]}}
            if resp.status_code not in (200,):
                return {"ok": False, "message": f"HTTP {resp.status_code}", "details": {"body": resp.text[:500]}}
            try:
                data = resp.json()
            except ValueError:
                data = {}
            return {"ok": True, "message": "Connected", "details": {"model_count": len(data.get("data", []))}}

    async def list_models(self) -> list[str]:
        async with build_client(self.config.timeout, headers=self._headers()) as client:
            resp = await request_with_retry(client, "GET", self._url("/models"), max_retries=1)
            if resp.status_code != 200:
                raise ConnectionFailedError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
            out = []
            for m in data.get("data", []):
                mid = m.get("id") or m.get("name")
                if mid:
                    out.append(mid)
            return out

    async def chat(self, request: ChatRequest) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.response_format is not None:
            payload["response_format"] = request.response_format
        if request.stream:
            payload["stream"] = True

        async with build_client(self.config.request_timeout, headers=self._headers()) as client:
            resp = await request_with_retry(client, "POST", self._url("/chat/completions"), json=payload,
                                           max_retries=self.config.max_retries)
            if resp.status_code != 200:
                raise ProviderError(f"Chat failed: HTTP {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
            choices = data.get("choices") or []
            text = ""
            finish = None
            if choices:
                msg = choices[0].get("message") or {}
                text = msg.get("content") or ""
                finish = choices[0].get("finish_reason")
            return ChatResponse(
                text=text,
                model=data.get("model", self.config.model),
                usage=data.get("usage") or {},
                raw=data,
                finish_reason=finish,
            )

    async def detect_capabilities(self) -> ModelCapabilities:
        caps = ModelCapabilities(streaming=True, structured_output=True)
        # Heuristic based on model name
        name = self.config.model.lower()
        if any(k in name for k in ("gpt-4o", "gpt-4-turbo", "vision", "llava", "claude-3", "gemini")):
            caps.image_input = True
        # probe context window unknown
        return caps