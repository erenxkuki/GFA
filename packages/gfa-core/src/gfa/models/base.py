"""Model provider abstraction and data types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class ModelCapabilities(BaseModel):
    text_generation: bool = True
    structured_output: bool = False
    image_input: bool = False
    streaming: bool = False
    tool_calling: bool = False
    embedding: bool = False
    context_window: int | None = None
    max_output_tokens: int | None = None


class ModelConfig(BaseModel):
    id: str = Field(..., description="Unique config id")
    provider: str
    endpoint: str
    model: str
    api_key: str | None = None
    timeout: float = 60.0
    request_timeout: float = 120.0
    max_retries: int = 2
    capabilities_override: dict[str, Any] | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: str  # system | user | assistant | tool
    content: str | list[dict[str, Any]] = ""
    name: str | None = None


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    response_format: dict[str, Any] | None = None  # e.g. {"type":"json_object"}
    stream: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    text: str
    model: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)
    finish_reason: str | None = None


@dataclass
class ProviderInfo:
    id: str
    name: str
    description: str = ""


class ModelProvider(ABC):
    """Abstract base for all model providers."""

    info: ProviderInfo

    def __init__(self, config: ModelConfig):
        self.config = config

    @abstractmethod
    async def test_connection(self) -> dict[str, Any]:
        """Return {ok: bool, message: str, details: dict}."""

    @abstractmethod
    async def list_models(self) -> list[str]:
        """List available model identifiers."""

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Non-streaming chat completion."""

    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:  # pragma: no cover
        raise NotImplementedError("Streaming not supported")
        yield  # type: ignore

    @abstractmethod
    async def detect_capabilities(self) -> ModelCapabilities:
        """Detect capabilities for the configured model."""