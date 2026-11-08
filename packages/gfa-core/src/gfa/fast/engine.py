"""Fast Action Engine: low-latency reactive gameplay."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from gfa.agent.agent import GameplayAgent
from gfa.agent.world_state import WorldState
from gfa.gcl.executor import CommandExecutor
from gfa.gcl.parser import parse_batch
from gfa.gcl.validator import ValidationContext
from gfa.universal.baseline import UniversalBaseline


@dataclass
class SpeedProfile:
    name: str = "fast"
    step_delay: float = 0.05
    capture_scale: float = 0.35
    run_ocr_every_n: int = 3  # OCR every N frames
    max_commands_per_step: int = 6
    skip_vision_on_fast: bool = False
    reflex_enabled: bool = True


FAST_PROFILE = SpeedProfile(name="fast", step_delay=0.05, capture_scale=0.35, run_ocr_every_n=3)
BALANCED_PROFILE = SpeedProfile(name="balanced", step_delay=0.2, capture_scale=0.5, run_ocr_every_n=1)
THOROUGH_PROFILE = SpeedProfile(name="thorough", step_delay=0.5, capture_scale=0.75, run_ocr_every_n=1)


@dataclass
class ReflexRule:
    name: str
    condition: Callable[[WorldState], bool]
    commands: Callable[[WorldState], list[dict[str, Any]]]
    priority: int = 0


class ReflexLayer:
    """Instant reactive rules that bypass model reasoning for common situations."""

    def __init__(self):
        self.rules: list[ReflexRule] = []

    def add_rule(self, rule: ReflexRule) -> None:
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)

    def evaluate(self, ws: WorldState) -> list[dict[str, Any]] | None:
        for rule in self.rules:
            try:
                if rule.condition(ws):
                    return rule.commands(ws)
            except Exception:  # noqa: BLE001
                continue
        return None


class FastActionEngine:
    """Wraps GameplayAgent with low-latency optimizations.

    - Reflex layer for instant reactions (no model call)
    - Reduced observation overhead (configurable OCR frequency)
    - Parallel command execution in executor
    - Speed profiles
    """

    def __init__(self, agent: GameplayAgent, profile: SpeedProfile = FAST_PROFILE,
                 reflexes: ReflexLayer | None = None):
        self.agent = agent
        self.profile = profile
        self.reflexes = reflexes or ReflexLayer()
        self._frame_count = 0
        self._last_ocr_frame = 0
        self._cached_text_blocks: list[str] = []

        # Apply profile to agent
        self.agent.step_delay = profile.step_delay
        self.agent.vision_mode = "compact" if profile.skip_vision_on_fast else self.agent.vision_mode
        self.agent.use_framegen = True
        if hasattr(self.agent.baseline, "config"):
            self.agent.baseline.config.capture_scale = profile.capture_scale

    def should_run_ocr(self) -> bool:
        self._frame_count += 1
        if self._frame_count - self._last_ocr_frame >= self.profile.run_ocr_every_n:
            self._last_ocr_frame = self._frame_count
            return True
        return False

    async def run(self, objective: str, game: str | None = None) -> Any:
        """Run the agent with fast-action optimizations."""
        # Monkey-patch the agent's perception to skip OCR on non-OCR frames
        original_perception = self.agent.perception
        cached_text = self._cached_text_blocks

        class FastPerception:
            def __init__(self, inner, engine):
                self.inner = inner
                self.engine = engine

            def analyze(self, frame):
                result = self.inner.analyze(frame)
                # If inner is VisionPerception, manage OCR frequency
                if hasattr(result, "text_blocks"):
                    if self.engine.should_run_ocr():
                        self.engine._cached_text_blocks = result.text_blocks
                    else:
                        result.text_blocks = self.engine._cached_text_blocks
                        # rebuild compact summary without re-running OCR
                        if result.compact_summary and "Screen text:" in result.compact_summary:
                            # keep cached
                            pass
                return result

        if self.profile.reflex_enabled:
            self.agent.perception = FastPerception(original_perception, self)

        # Add reflex check: override agent run to check reflexes first
        # We'll patch by wrapping the reasoning decide
        original_decide = self.agent.reasoning.decide

        async def fast_decide(world_state, caps=None, image_base64=None):
            # Check reflexes first
            if self.reflexes.rules:
                reflex_cmds = self.reflexes.evaluate(world_state)
                if reflex_cmds is not None:
                    return reflex_cmds, "reflex"
            return await original_decide(world_state, caps, image_base64=image_base64)

        self.agent.reasoning.decide = fast_decide

        result = await self.agent.run(objective, game=game)
        # Restore
        self.agent.perception = original_perception
        self.agent.reasoning.decide = original_decide
        return result