"""Real-time action agent for fast-paced games."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from gfa.agent.agent import GameplayAgent
from gfa.agent.world_state import WorldState
from gfa.fast.engine import FastActionEngine, ReflexLayer
from gfa.realtime.profiles import GenreProfile, GENRE_PROFILES
from gfa.realtime.tracking import MotionTracker


@dataclass
class RealtimeConfig:
    genre: str = "shooter"
    profile: GenreProfile | None = None
    duration_seconds: float = 30.0
    reflexes: ReflexLayer | None = None

    def __post_init__(self):
        if self.profile is None:
            self.profile = GENRE_PROFILES.get(self.genre, GENRE_PROFILES["shooter"])


class RealtimeAgent:
    """High-frequency game loop for fast-paced games.

    Runs at target_fps, uses reflexes for instant reactions,
    motion tracking for prediction, and model reasoning at reduced rate.
    """

    def __init__(self, gameplay_agent: GameplayAgent, config: RealtimeConfig | None = None):
        self.agent = gameplay_agent
        self.config = config or RealtimeConfig()
        profile = self.config.profile
        # Apply profile
        self.agent.step_delay = profile.step_delay
        self.agent.vision_mode = "compact"
        if hasattr(self.agent.baseline, "config"):
            self.agent.baseline.config.capture_scale = profile.capture_scale
        self.tracker = MotionTracker(lookahead=profile.max_lookahead_ms / 1000.0)
        self.reflexes = self.config.reflexes or ReflexLayer()
        self._running = False
        self._frame_count = 0
        self._last_model_call = 0.0
        self._model_interval = 1.0 / max(1, profile.target_fps // 3)  # model runs at 1/3 perception rate
        self.results: list[dict[str, Any]] = []

    async def run(self, objective: str, game: str | None = None) -> dict[str, Any]:
        self._running = True
        start = time.time()
        end_time = start + self.config.duration_seconds
        frames = 0
        reflex_hits = 0
        model_calls = 0

        while self._running and time.time() < end_time:
            frame_start = time.time()
            try:
                frame = self.agent.baseline.observe()
            except Exception:  # noqa: BLE001
                await asyncio.sleep(self.config.profile.step_delay)
                continue

            # Track objects
            if hasattr(self.agent.perception, "analyze"):
                try:
                    r = self.agent.perception.analyze(frame)
                    objs = r.objects if hasattr(r, "objects") else (r if isinstance(r, list) else [])
                    self.tracker.update_many([{"label": o.label, "x": o.x, "y": o.y} for o in objs])
                except Exception:  # noqa: BLE001
                    objs = []

            frames += 1
            self._frame_count += 1

            # Build world state
            ws = WorldState(
                game=game, current_context="gameplay",
                visible_objects=[{"label": o.label, "x": o.x, "y": o.y} for o in objs] if objs else [],
                objectives=[objective],
            )

            # Try reflex first
            reflex_cmds = self.reflexes.evaluate(ws) if self.reflexes.rules else None
            if reflex_cmds is not None:
                reflex_hits += 1
                caps = self.agent.baseline.capabilities()
                from gfa.gcl.validator import ValidationContext
                ctx = ValidationContext(capabilities=caps)
                batch = parse_batch({"protocol": "gcl-v1", "commands": reflex_cmds})
                vr = self.agent.validator.validate_batch(batch, ctx)
                if vr.ok:
                    await self.agent.executor.execute_batch(batch, ctx)
                self.results.append({"type": "reflex", "commands": reflex_cmds})
                # maintain frame rate
                elapsed = time.time() - frame_start
                sleep = max(0, self.config.profile.step_delay - elapsed)
                await asyncio.sleep(sleep)
                continue

            # Model reasoning at reduced rate
            now = time.time()
            if now - self._last_model_call >= self._model_interval:
                self._last_model_call = now
                model_calls += 1
                try:
                    commands, reasoning = await self.agent.reasoning.decide(ws, [])
                    if commands:
                        caps = self.agent.baseline.capabilities()
                        from gfa.gcl.validator import ValidationContext
                        ctx = ValidationContext(capabilities=caps)
                        batch = parse_batch({"protocol": "gcl-v1", "commands": commands})
                        vr = self.agent.validator.validate_batch(batch, ctx)
                        if vr.ok:
                            await self.agent.executor.execute_batch(batch, ctx)
                        self.results.append({"type": "model", "commands": commands, "reasoning": reasoning})
                except Exception:  # noqa: BLE001
                    pass

            elapsed = time.time() - frame_start
            sleep = max(0, self.config.profile.step_delay - elapsed)
            await asyncio.sleep(sleep)

        self._running = False
        return {
            "frames": frames,
            "reflex_hits": reflex_hits,
            "model_calls": model_calls,
            "duration": time.time() - start,
            "fps": frames / max(0.001, time.time() - start),
        }

    def stop(self) -> None:
        self._running = False