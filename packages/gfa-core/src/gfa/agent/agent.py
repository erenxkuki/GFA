"""Autonomous gameplay agent loop."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from gfa.agent.perception import PerceptionEngine, ColorBlobPerception
from gfa.agent.planning import PlanningEngine
from gfa.agent.reasoning import ReasoningCoordinator
from gfa.agent.world_state import WorldState
from gfa.gcl.executor import CommandExecutor
from gfa.gcl.parser import parse_batch
from gfa.gcl.schema import CommandStatus
from gfa.gcl.validator import GCLValidator, ValidationContext
from gfa.universal.baseline import UniversalBaseline

try:
    from gfa.memory.manager import MemoryManager
    from gfa.memory.extractor import ExperienceExtractor
except Exception:  # noqa: BLE001
    MemoryManager = None  # type: ignore
    ExperienceExtractor = None  # type: ignore


@dataclass
class AgentResult:
    success: bool
    steps: int
    reason: str
    action_history: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class GameplayAgent:
    def __init__(
        self,
        baseline: UniversalBaseline,
        reasoning: ReasoningCoordinator,
        perception: PerceptionEngine | None = None,
        planning: PlanningEngine | None = None,
        executor: CommandExecutor | None = None,
        validator: GCLValidator | None = None,
        memory_manager=None,
        game_id: str | None = None,
        session_id: str | None = None,
        model_provenance: str | None = None,
        objective_check=None,  # callable(world_state) -> bool
        max_steps: int = 20,
        step_delay: float = 0.5,
    ):
        self.baseline = baseline
        self.reasoning = reasoning
        self.perception = perception or ColorBlobPerception()
        self.planning = planning or PlanningEngine()
        self.executor = executor or CommandExecutor()
        self.validator = validator or GCLValidator()
        self.memory_manager = memory_manager
        self.game_id = game_id
        self.session_id = session_id
        self.model_provenance = model_provenance
        self.objective_check = objective_check
        self.max_steps = max_steps
        self.step_delay = step_delay
        self._emergency = False
        self.action_history: list[dict[str, Any]] = []
        self.errors: list[str] = []

    def emergency_stop(self) -> None:
        self._emergency = True
        self.baseline.emergency_stop()

    async def run(self, objective: str, game: str | None = None) -> AgentResult:
        self.baseline.register_gcl_handlers(self.executor)
        caps = self.baseline.capabilities()
        ctx = ValidationContext(capabilities=caps, max_commands_per_batch=8)
        recent: list[dict[str, Any]] = []

        for step in range(self.max_steps):
            if self._emergency:
                return AgentResult(False, step, "emergency stop", self.action_history, self.errors)
            try:
                frame = self.baseline.observe()
            except Exception as exc:  # noqa: BLE001
                self.errors.append(f"observe failed: {exc}")
                await asyncio.sleep(self.step_delay)
                continue

            objects = self.perception.analyze(frame)
            retrieved = []
            if self.memory_manager is not None:
                try:
                    recs = self.memory_manager.retrieve_for_context(self.game_id or game, objective, limit=5)
                    retrieved = [r.to_dict() if hasattr(r, "to_dict") else {"content": str(r)} for r in recs]
                except Exception:  # noqa: BLE001
                    retrieved = []
            ws = WorldState(
                game=game,
                current_context="gameplay",
                visible_objects=[{"label": o.label, "x": o.x, "y": o.y, "w": o.w, "h": o.h,
                                 "confidence": o.confidence} for o in objects],
                retrieved_memories=retrieved,
                objectives=[objective],
                recent_actions=recent[-5:],
                available_capabilities=sorted(caps.capabilities),
                observation_summary=f"frame {frame.width}x{frame.height}",
            )

            # objective check
            if self.objective_check is not None and self.objective_check(ws):
                return AgentResult(True, step, "objective met", self.action_history, self.errors)

            commands, reasoning_text = await self.reasoning.decide(ws, sorted(caps.capabilities))

            if not commands:
                self.errors.append("no commands from reasoning")
                await asyncio.sleep(self.step_delay)
                continue

            # validate
            try:
                batch = parse_batch({"protocol": "gcl-v1", "commands": commands})
            except Exception as exc:  # noqa: BLE001
                self.errors.append(f"parse failed: {exc}")
                recent.append({"commands": commands, "result": "parse_error", "error": str(exc)})
                await asyncio.sleep(self.step_delay)
                continue

            vr = self.validator.validate_batch(batch, ctx)
            if not vr.ok:
                self.errors.append("validation failed: " + "; ".join(vr.errors))
                recent.append({"commands": commands, "result": "validation_error", "errors": vr.errors})
                await asyncio.sleep(self.step_delay)
                continue

            # execute
            try:
                results = await self.executor.execute_batch(batch, ctx)
            except Exception as exc:  # noqa: BLE001
                self.errors.append(f"execution failed: {exc}")
                await asyncio.sleep(self.step_delay)
                continue

            entry = {"step": step, "reasoning": reasoning_text, "commands": commands,
                     "results": [r.status.value for r in results]}
            recent.append(entry)
            self.action_history.append(entry)

            # Memory extraction
            if self.memory_manager is not None and ExperienceExtractor is not None:
                try:
                    extractor = ExperienceExtractor(game_id=self.game_id or game, session_id=self.session_id,
                                                   model_provenance=self.model_provenance)
                    success = all(r.status.value == "succeeded" for r in results) if results else False
                    exps = extractor.extract({
                        "action": commands, "result": {"ok": success}, "success": success,
                        "objective": objective, "context": reasoning_text,
                    })
                    for m in exps:
                        self.memory_manager.add(m)
                except Exception:  # noqa: BLE001
                    pass

            # check objective again after actions
            if self.objective_check is not None:
                # re-observe quickly
                try:
                    frame2 = self.baseline.observe()
                    objects2 = self.perception.analyze(frame2)
                    ws2 = WorldState(game=game, visible_objects=[{"label": o.label, "x": o.x, "y": o.y} for o in objects2],
                                     objectives=[objective])
                    if self.objective_check(ws2):
                        return AgentResult(True, step + 1, "objective met", self.action_history, self.errors)
                except Exception:  # noqa: BLE001
                    pass

            await asyncio.sleep(self.step_delay)

        return AgentResult(False, self.max_steps, "max steps reached", self.action_history, self.errors)