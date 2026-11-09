"""Autonomous gameplay agent loop."""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from typing import Any

from gfa.agent.perception import PerceptionEngine, ColorBlobPerception
try:
    from gfa.vision.perception import VisionPerception, PerceptionResult
    from gfa.vision.optimizer import TokenOptimizer
    from gfa.vision.framegen.generator import FrameGenerator, GeneratedFrame
except Exception:  # noqa: BLE001
    VisionPerception = None  # type: ignore
    PerceptionResult = None  # type: ignore
    TokenOptimizer = None  # type: ignore
    FrameGenerator = None  # type: ignore
    GeneratedFrame = None  # type: ignore
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
        vision_mode: str = "compact",  # compact | hybrid | full
        use_vision: bool = True,
        use_framegen: bool = False,
        objective_check=None,  # callable(world_state) -> bool
        max_steps: int = 20,
        step_delay: float = 0.5,
        audio_monitor=None,  # gfa.audio.AudioMonitor | None
        recorder=None,  # gfa.replay.SessionRecorder | None
        feedback_injector=None,  # gfa.feedback.FeedbackInjector | None
        world_model=None,  # gfa.worldmodel.WorldModelPredictor | None
        reward_tracker=None,  # gfa.rl.RewardTracker | None
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
        self.vision_mode = vision_mode
        self.use_vision = use_vision
        self.use_framegen = use_framegen
        self._framegen = None
        self.objective_check = objective_check
        self.max_steps = max_steps
        self.step_delay = step_delay
        self.audio_monitor = audio_monitor
        self.recorder = recorder
        self.feedback_injector = feedback_injector
        self.world_model = world_model
        self.reward_tracker = reward_tracker
        self._macro_recorder = None
        self._macro_name: str | None = None
        self._emergency = False
        self.action_history: list[dict[str, Any]] = []
        self.errors: list[str] = []

    def start_macro_recording(self, name: str, game: str | None = None) -> None:
        """Begin recording executed steps into a named macro (saved on stop)."""
        from gfa.macros.recorder import MacroRecorder

        self._macro_recorder = MacroRecorder(name=name, game=game or self.game_id, source="agent")
        self._macro_recorder.start_recording()
        self._macro_name = name

    def stop_macro_recording(self) -> dict[str, Any] | None:
        """Finish recording and save the macro to the baseline library."""
        if getattr(self, "_macro_recorder", None) is None or not self._macro_recorder.recording:
            return None
        macro = self._macro_recorder.stop_recording()
        self._macro_recorder = None
        try:
            self.baseline.macros.save(macro)
        except Exception:  # noqa: BLE001
            return None
        return macro.to_dict()

    def _record_macro_step(self, commands: Any) -> None:
        if getattr(self, "_macro_recorder", None) is not None and self._macro_recorder.recording:
            with contextlib.suppress(Exception):  # noqa: BLE001
                self._macro_recorder.record(commands)

    def emergency_stop(self) -> None:
        self._emergency = True
        self.baseline.emergency_stop()

    def _record_step(self, step: int, frame=None, observation_summary: str = "",
                     objects: Any = None, reasoning: str = "", commands: Any = None,
                     results: Any = None, audio_events: Any = None,
                     latency_ms: Any = None, error: str | None = None) -> None:
        """Record a step to the session replay (no-op if no recorder)."""
        if self.recorder is None:
            return
        with contextlib.suppress(Exception):  # noqa: BLE001 - recording never breaks gameplay
            self.recorder.record_step(step, frame=frame, observation_summary=observation_summary,
                                      objects=objects, reasoning=reasoning, commands=commands,
                                      results=results, audio_events=audio_events,
                                      latency_ms=latency_ms, error=error)

    def _finish_recording(self, success: bool, reason: str = "") -> None:
        if self.recorder is None:
            return
        with contextlib.suppress(Exception):  # noqa: BLE001
            self.recorder.finish(success, reason=reason,
                                 summary=f"{len(self.action_history)} actions, {len(self.errors)} errors")

    async def run(self, objective: str, game: str | None = None) -> AgentResult:
        if self.recorder is not None:
            with contextlib.suppress(Exception):  # noqa: BLE001
                self.recorder.start()
        self.baseline.register_gcl_handlers(self.executor)
        caps = self.baseline.capabilities()
        ctx = ValidationContext(capabilities=caps, max_commands_per_batch=8)
        recent: list[dict[str, Any]] = []

        for step in range(self.max_steps):
            if self._emergency:
                self._finish_recording(False, "emergency stop")
                return AgentResult(False, step, "emergency stop", self.action_history, self.errors)
            try:
                frame = self.baseline.observe()
            except Exception as exc:  # noqa: BLE001
                self.errors.append(f"observe failed: {exc}")
                self._record_step(step, error=f"observe failed: {exc}")
                await asyncio.sleep(self.step_delay)
                continue

            # Perception
            compact_summary = f"frame {frame.width}x{frame.height}"
            vision_result = None
            objects = []

            if self.use_vision and VisionPerception is not None and isinstance(self.perception, VisionPerception):
                if self.use_framegen and FrameGenerator is not None:
                    if self._framegen is None:
                        self._framegen = FrameGenerator(self.perception)
                    gen = self._framegen.process(frame)
                    vision_result = gen.result
                    objects = vision_result.objects
                    compact_summary = vision_result.compact_summary
                    if not gen.is_real:
                        compact_summary += " [interpolated]"
                else:
                    vision_result = self.perception.analyze(frame)
                    objects = vision_result.objects
                    compact_summary = vision_result.compact_summary
            elif hasattr(self.perception, "analyze"):
                r = self.perception.analyze(frame)
                if isinstance(r, list):
                    objects = r
                elif PerceptionResult is not None and isinstance(r, PerceptionResult):
                    vision_result = r
                    objects = r.objects
                    compact_summary = r.compact_summary
                else:
                    objects = []

            # Spatial awareness
            spatial_text = ""
            try:
                from gfa.spatial.depth import SpatialEstimator
                se = SpatialEstimator(frame_width=frame.width, frame_height=frame.height)
                if objects:
                    spatial_text = se.spatial_summary([{"label": o.label, "x": o.x, "y": o.y, "w": o.w, "h": o.h} for o in objects])
            except Exception:  # noqa: BLE001
                spatial_text = ""

            # Audio awareness: poll detected sound events into the world state
            audio_text = ""
            if self.audio_monitor is not None:
                try:
                    audio_events = self.audio_monitor.poll()
                    if audio_events:
                        audio_text = "Audio: " + "; ".join(
                            f"{e.category}(conf={e.confidence:.2f})" for e in audio_events[-8:])
                except Exception:  # noqa: BLE001
                    audio_text = ""

            # World model: track motion and predict next-state threats
            prediction_text = ""
            incoming_threats: list[dict[str, Any]] = []
            if self.world_model is not None:
                try:
                    prediction = self.world_model.update(objects, step=step)
                    prediction_text = prediction.to_text()
                    incoming_threats = [t.to_dict() for t in prediction.incoming_threats]
                except Exception:  # noqa: BLE001
                    prediction_text = ""
                    incoming_threats = []

            # Human feedback: inject pending human corrections into the world state
            feedback_text = ""
            if self.feedback_injector is not None:
                try:
                    feedback_text = self.feedback_injector.inject(game=self.game_id or game)
                except Exception:  # noqa: BLE001
                    feedback_text = ""

            # RL: observe rewards from the current observation summary
            reward_text = ""
            if self.reward_tracker is not None:
                try:
                    self.reward_tracker.observe(compact_summary, step=step)
                    reward_text = self.reward_tracker.reward_context()
                except Exception:  # noqa: BLE001
                    reward_text = ""

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
                observation_summary=(compact_summary + (f" Spatial: {spatial_text}" if spatial_text else "")
                                     + (f" Audio: {audio_text}" if audio_text else "")
                                     + (f" {feedback_text}" if feedback_text else "")
                                     + (f" {prediction_text}" if prediction_text else "")
                                     + (f" {reward_text}" if reward_text else "")),
                incoming_threats=incoming_threats,
                reward_summary=reward_text,
            )

            # Token optimization: decide whether to send image
            image_b64 = None
            if self.vision_mode in ("full", "hybrid"):
                image_b64 = frame.to_base64()

            # objective check
            if self.objective_check is not None and self.objective_check(ws):
                self._finish_recording(True, "objective met")
                return AgentResult(True, step, "objective met", self.action_history, self.errors)

            commands, reasoning_text = await self.reasoning.decide(ws, sorted(caps.capabilities), image_base64=image_b64)

            if not commands:
                self.errors.append("no commands from reasoning")
                self._record_step(step, frame=frame, observation_summary=ws.observation_summary,
                                  objects=[{"label": o.label, "x": o.x, "y": o.y} for o in objects],
                                  reasoning=reasoning_text, error="no commands from reasoning")
                await asyncio.sleep(self.step_delay)
                continue

            # validate
            try:
                batch = parse_batch({"protocol": "gcl-v1", "commands": commands})
            except Exception as exc:  # noqa: BLE001
                self.errors.append(f"parse failed: {exc}")
                recent.append({"commands": commands, "result": "parse_error", "error": str(exc)})
                self._record_step(step, frame=frame, reasoning=reasoning_text, commands=commands,
                                  error=f"parse failed: {exc}")
                await asyncio.sleep(self.step_delay)
                continue

            vr = self.validator.validate_batch(batch, ctx)
            if not vr.ok:
                self.errors.append("validation failed: " + "; ".join(vr.errors))
                recent.append({"commands": commands, "result": "validation_error", "errors": vr.errors})
                self._record_step(step, frame=frame, reasoning=reasoning_text, commands=commands,
                                  error="validation failed: " + "; ".join(vr.errors))
                await asyncio.sleep(self.step_delay)
                continue

            # execute
            try:
                results = await self.executor.execute_batch(batch, ctx)
            except Exception as exc:  # noqa: BLE001
                self.errors.append(f"execution failed: {exc}")
                self._record_step(step, frame=frame, reasoning=reasoning_text, commands=commands,
                                  error=f"execution failed: {exc}")
                await asyncio.sleep(self.step_delay)
                continue

            entry = {"step": step, "reasoning": reasoning_text, "commands": commands,
                     "results": [r.status.value for r in results]}
            recent.append(entry)
            self.action_history.append(entry)

            # Corrections were visible to the model for this action: mark applied + learn
            if self.feedback_injector is not None:
                with contextlib.suppress(Exception):  # noqa: BLE001
                    self.feedback_injector.consume_after_action()

            # Macro recording: capture this executed step
            self._record_macro_step(commands)

            # RL: score the executed commands with the latest reward
            if self.reward_tracker is not None:
                with contextlib.suppress(Exception):  # noqa: BLE001
                    self.reward_tracker.score_action(commands)

            self._record_step(step, frame=frame, observation_summary=ws.observation_summary,
                              objects=[{"label": o.label, "x": o.x, "y": o.y, "w": o.w, "h": o.h,
                                        "confidence": o.confidence} for o in objects],
                              reasoning=reasoning_text, commands=commands,
                              results=[r.status.value for r in results],
                              audio_events=audio_text or None)

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
                        self._finish_recording(True, "objective met")
                        return AgentResult(True, step + 1, "objective met", self.action_history, self.errors)
                except Exception:  # noqa: BLE001
                    pass

            await asyncio.sleep(self.step_delay)

        self._finish_recording(False, "max steps reached")
        return AgentResult(False, self.max_steps, "max steps reached", self.action_history, self.errors)