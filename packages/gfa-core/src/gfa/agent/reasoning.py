"""Reasoning coordinator: converts world state into GCL commands via a model."""

from __future__ import annotations

import json
import re
from typing import Any

from gfa.models.base import ChatMessage, ChatRequest, ModelProvider
from gfa.shared.errors import ProviderError


SYSTEM_PROMPT = """You are an AI playing a video game through GFA.
You receive the current world state and must decide the next actions.
Respond ONLY with a JSON object of the form:
{"reasoning": "<short reason>", "commands": [ <GCL command objects> ]}
GCL commands are JSON objects with a "type" field. Allowed types: observe, move, click, scroll, key, type_text, wait, verify, emergency_stop.
For movement use {"type":"move","direction":"forward|backward|left|right|up|down","duration_ms":<int>}.
Keep commands to a short, safe batch (max 4). Never include explanations outside JSON."""


class ReasoningCoordinator:
    def __init__(self, model_provider: ModelProvider | None = None, fallback_policy=None):
        self.model = model_provider
        self.fallback_policy = fallback_policy  # callable(world_state) -> list[dict]

    async def decide(self, world_state, available_capabilities: list[str] | None = None,
                     image_base64: str | None = None) -> tuple[list[dict[str, Any]], str]:
        prompt = world_state.to_prompt_text() if hasattr(world_state, "to_prompt_text") else str(world_state)
        if available_capabilities:
            prompt += "\nAvailable capabilities: " + ", ".join(available_capabilities)
        prompt += "\nReturn JSON only."

        # Build message content (text + optional image)
        if image_base64:
            content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
            ]
        else:
            content = prompt

        # Try model first
        if self.model is not None:
            try:
                req = ChatRequest(messages=[
                    ChatMessage(role="system", content=SYSTEM_PROMPT),
                    ChatMessage(role="user", content=content),
                ], response_format={"type": "json_object"}, max_tokens=512)
                resp = await self.model.chat(req)
                cmds, reasoning = self._parse(resp.text)
                if cmds is not None:
                    return cmds, reasoning
            except Exception as exc:  # noqa: BLE001
                # fall through to fallback
                world_state.uncertainty.append(f"model error: {exc}")

        # Fallback policy
        if self.fallback_policy is not None:
            try:
                cmds = self.fallback_policy(world_state)
                return cmds, "fallback policy"
            except Exception as exc:  # noqa: BLE001
                world_state.uncertainty.append(f"fallback error: {exc}")

        return [], "no decision"

    @staticmethod
    def _parse(text: str) -> tuple[list[dict[str, Any]] | None, str]:
        # strip code fences
        t = text.strip()
        m = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
        if m:
            t = m.group(1).strip()
        # find first JSON object
        start = t.find("{")
        end = t.rfind("}")
        if start == -1 or end == -1:
            return None, ""
        try:
            obj = json.loads(t[start:end + 1])
        except json.JSONDecodeError:
            return None, ""
        reasoning = obj.get("reasoning", "") if isinstance(obj, dict) else ""
        commands = None
        if isinstance(obj, dict):
            if isinstance(obj.get("commands"), list):
                commands = obj["commands"]
            elif isinstance(obj.get("gcl"), dict) and isinstance(obj["gcl"].get("commands"), list):
                commands = obj["gcl"]["commands"]
            elif isinstance(obj.get("actions"), list):
                commands = obj["actions"]
        if commands is None:
            return None, reasoning
        # ensure list of dicts
        cmds = [c for c in commands if isinstance(c, dict) and "type" in c]
        return cmds, reasoning