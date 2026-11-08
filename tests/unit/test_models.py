import httpx
import pytest
from gfa.models.base import ChatMessage, ChatRequest, ModelConfig
from gfa.models.providers.ollama import OllamaProvider
from gfa.models.providers.openai_compat import OpenAICompatibleProvider


def mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_ollama_connection_and_chat(monkeypatch):
    def handler(request):
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.3.0"})
        if request.url.path == "/api/chat":
            return httpx.Response(200, json={"model": "llama3", "message": {"content": "hello from ollama"},
                                             "done_reason": "stop", "prompt_eval_count": 5, "eval_count": 3})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "llama3"}]})
        return httpx.Response(404)

    import gfa.models.http as httpmod

    def patched(timeout, headers=None):
        return httpx.AsyncClient(transport=mock_transport(handler), timeout=timeout, headers=headers or {})

    monkeypatch.setattr(httpmod, "build_client", patched)
    # also patch references imported in provider modules
    import gfa.models.providers.ollama as omod
    import gfa.models.providers.openai_compat as cmod
    monkeypatch.setattr(omod, "build_client", patched)
    monkeypatch.setattr(cmod, "build_client", patched)

    cfg = ModelConfig(id="m1", provider="ollama", endpoint="http://localhost:11434", model="llama3")
    p = OllamaProvider(cfg)
    r = await p.test_connection()
    assert r["ok"] is True
    models = await p.list_models()
    assert "llama3" in models
    resp = await p.chat(ChatRequest(messages=[ChatMessage(role="user", content="hi")]))
    assert resp.text == "hello from ollama"


@pytest.mark.asyncio
async def test_openai_compat_chat(monkeypatch):
    def handler(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gpt-4o-mini"}]})
        if request.url.path.endswith("/chat/completions"):
            return httpx.Response(200, json={"model": "gpt-4o-mini",
                                            "choices": [{"message": {"content": "hi there"}, "finish_reason": "stop"}],
                                            "usage": {"total_tokens": 10}})
        return httpx.Response(404)

    import gfa.models.http as httpmod

    def patched(timeout, headers=None):
        return httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=timeout, headers=headers or {})

    monkeypatch.setattr(httpmod, "build_client", patched)
    import gfa.models.providers.openai_compat as cmod
    monkeypatch.setattr(cmod, "build_client", patched)

    cfg = ModelConfig(id="m2", provider="openai", endpoint="https://api.openai.com/v1", model="gpt-4o-mini", api_key="sk-test")
    p = OpenAICompatibleProvider(cfg)
    r = await p.test_connection()
    assert r["ok"] is True
    resp = await p.chat(ChatRequest(messages=[ChatMessage(role="user", content="hi")]))
    assert resp.text == "hi there"