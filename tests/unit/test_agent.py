import asyncio
from unittest.mock import AsyncMock

from gfa.agent.agent import GameplayAgent
from gfa.agent.perception import ColorBlobPerception
from gfa.agent.reasoning import ReasoningCoordinator
from gfa.agent.world_state import WorldState
from gfa.models.base import ChatMessage, ChatRequest, ChatResponse, ModelConfig, ModelProvider
from gfa.universal.baseline import BaselineConfig, UniversalBaseline


class MockModel(ModelProvider):
    info = None

    def __init__(self):
        super().__init__(ModelConfig(id="m", provider="openai", endpoint="http://x", model="gpt"))

    async def test_connection(self):
        return {"ok": True, "message": "ok", "details": {}}

    async def list_models(self):
        return ["gpt"]

    async def chat(self, request: ChatRequest) -> ChatResponse:
        # Always move right
        return ChatResponse(text='{"reasoning":"move right","commands":[{"type":"move","direction":"right","duration_ms":100}]}')

    async def detect_capabilities(self):
        from gfa.models.base import ModelCapabilities
        return ModelCapabilities()


def test_reasoning_with_model():
    async def run():
        model = MockModel()
        rc = ReasoningCoordinator(model_provider=model)
        ws = WorldState(objectives=["reach target"], visible_objects=[{"label": "blue", "x": 10, "y": 10}])
        cmds, reasoning = await rc.decide(ws, ["gcl.move"])
        assert len(cmds) == 1
        assert cmds[0]["type"] == "move"
        assert "right" in reasoning or reasoning
    asyncio.run(run())


def test_reasoning_fallback_on_bad_json():
    class BadModel(ModelProvider):
        info = None
        def __init__(self):
            super().__init__(ModelConfig(id="m", provider="openai", endpoint="http://x", model="gpt"))
        async def test_connection(self):
            return {"ok": True, "message": "ok", "details": {}}
        async def list_models(self):
            return []
        async def chat(self, request):
            return ChatResponse(text="not json")
        async def detect_capabilities(self):
            from gfa.models.base import ModelCapabilities
            return ModelCapabilities()

    async def run():
        rc = ReasoningCoordinator(model_provider=BadModel(), fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 10}])
        ws = WorldState(objectives=["x"])
        cmds, reasoning = await rc.decide(ws)
        assert cmds and cmds[0]["type"] == "wait"
    asyncio.run(run())


def test_parse_handles_code_fence():
    from gfa.agent.reasoning import ReasoningCoordinator
    cmds, reasoning = ReasoningCoordinator._parse("```json\n{\"reasoning\":\"r\",\"commands\":[{\"type\":\"wait\"}]}\n```")
    assert cmds == [{"type": "wait"}]