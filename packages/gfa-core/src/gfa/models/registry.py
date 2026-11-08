"""Provider registry and factory."""

from __future__ import annotations

from gfa.models.base import ModelConfig, ModelProvider
from gfa.models.providers.ollama import OllamaProvider
from gfa.models.providers.openai_compat import OpenAICompatibleProvider
from gfa.shared.errors import ConfigurationError

_PROVIDER_CLASSES: dict[str, type] = {
    "ollama": OllamaProvider,
    "openai": OpenAICompatibleProvider,
    "openai-compatible": OpenAICompatibleProvider,
    "openai_compatible": OpenAICompatibleProvider,
    "lmstudio": OpenAICompatibleProvider,
    "lm-studio": OpenAICompatibleProvider,
    "custom": OpenAICompatibleProvider,
}

DEFAULT_ENDPOINTS = {
    "ollama": "http://localhost:11434",
    "openai": "https://api.openai.com/v1",
    "lmstudio": "http://localhost:1234/v1",
    "lm-studio": "http://localhost:1234/v1",
}


def normalize_provider(name: str) -> str:
    return name.strip().lower()


def get_provider_class(name: str):
    key = normalize_provider(name)
    if key not in _PROVIDER_CLASSES:
        raise ConfigurationError(f"Unknown provider: {name}", code="unknown_provider")
    return _PROVIDER_CLASSES[key]


def create_provider(config: ModelConfig) -> ModelProvider:
    cls = get_provider_class(config.provider)
    # Fill default endpoint if missing/empty
    if not config.endpoint:
        key = normalize_provider(config.provider)
        if key in DEFAULT_ENDPOINTS:
            config.endpoint = DEFAULT_ENDPOINTS[key]
    return cls(config)  # type: ignore[call-arg]


def list_providers() -> list[dict[str, str]]:
    return [
        {"id": "ollama", "name": "Ollama"},
        {"id": "openai", "name": "OpenAI"},
        {"id": "lmstudio", "name": "LM Studio"},
        {"id": "openai-compatible", "name": "OpenAI-Compatible / Custom"},
    ]