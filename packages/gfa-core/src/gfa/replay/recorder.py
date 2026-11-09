"""Session replay: record and inspect gameplay sessions.

A replay is a directory under ``<data_dir>/replays/<session_id>/``::

    manifest.json        - session metadata (game, model, objective, timing, result)
    frames/frame_00000.png, frame_00001.png, ...  - one screenshot per step
    events.jsonl         - one JSON object per step: observation, reasoning, commands, results

The :class:`SessionRecorder` is fed by the gameplay agent during a run; the
:class:`ReplayViewer` loads a finished replay and supports timeline scrubbing
(:meth:`ReplayViewer.step_at`), frame lookup, and human-readable summaries.
"""

from __future__ import annotations

import contextlib
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class ReplayManifest:
    """Session metadata written to ``manifest.json``."""

    session_id: str
    game: str | None = None
    model: str | None = None
    objective: str | None = None
    started_at: str = field(default_factory=_iso_now)
    ended_at: str | None = None
    duration_s: float = 0.0
    steps: int = 0
    frames: int = 0
    success: bool = False
    reason: str = ""
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "game": self.game,
            "model": self.model,
            "objective": self.objective,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_s": self.duration_s,
            "steps": self.steps,
            "frames": self.frames,
            "success": self.success,
            "reason": self.reason,
            "summary": self.summary,
            "metadata": self.metadata,
        }

    def to_text(self) -> str:
        lines = [
            f"Session {self.session_id}",
            f"  Game: {self.game or '-'}",
            f"  Model: {self.model or '-'}",
            f"  Objective: {self.objective or '-'}",
            f"  Started: {self.started_at}  Ended: {self.ended_at or '-'}",
            f"  Duration: {self.duration_s:.1f}s  Steps: {self.steps}  Frames: {self.frames}",
            f"  Result: {'SUCCESS' if self.success else 'FAILED'} ({self.reason or '-'})",
        ]
        if self.summary:
            lines.append(f"  Summary: {self.summary}")
        return "\n".join(lines)


class SessionRecorder:
    """Records one gameplay session to disk for later replay/inspection.

    Lifecycle: construct (or :meth:`for_run`), :meth:`start`, call
    :meth:`record_step` once per agent loop iteration, then :meth:`finish`.
    All public methods are safe to call even if recording is broken — none of
    them raise — so recording can never interrupt gameplay.
    """

    def __init__(self, data_dir: Path, session_id: str | None = None, game: str | None = None,
                 model: str | None = None, objective: str | None = None):
        self.data_dir = Path(data_dir)
        self.session_id = session_id or f"ses_{uuid.uuid4().hex[:12]}"
        self.manifest = ReplayManifest(session_id=self.session_id, game=game, model=model, objective=objective)
        self._dir = self.data_dir / "replays" / self.session_id
        self._frames_dir = self._dir / "frames"
        self._events_path = self._dir / "events.jsonl"
        self._started_mono = 0.0
        self._started = False
        self._finished = False

    @property
    def replay_dir(self) -> Path:
        return self._dir

    def start(self) -> Path:
        """Create the session directory. Idempotent."""
        try:
            self._frames_dir.mkdir(parents=True, exist_ok=True)
            self._started_mono = time.monotonic()
            self.manifest.started_at = _iso_now()
            self._started = True
        except Exception:  # noqa: BLE001 - recording must never break gameplay
            pass
        return self._dir

    def record_step(self, step: int, frame: Any = None, observation_summary: str = "",
                    objects: Any = None, reasoning: str = "", commands: Any = None,
                    results: Any = None, audio_events: Any = None,
                    latency_ms: Any = None, error: str | None = None) -> None:
        """Record one agent loop step: screenshot + what the agent saw/thought/did."""
        try:
            if not self._started:
                self.start()
            event: dict[str, Any] = {
                "type": "step",
                "step": step,
                "t_offset_ms": round((time.monotonic() - self._started_mono) * 1000.0, 1),
                "timestamp": _iso_now(),
                "observation_summary": observation_summary,
                "objects": objects or [],
                "reasoning": reasoning,
                "commands": commands or [],
                "results": results or [],
                "audio_events": audio_events or [],
                "latency_ms": latency_ms,
                "error": error,
                "frame": None,
            }
            if frame is not None:
                fname = f"frame_{step:05d}.png"
                try:
                    (self._frames_dir / fname).write_bytes(frame.png_bytes)
                    event["frame"] = f"frames/{fname}"
                    self.manifest.frames += 1
                except Exception:  # noqa: BLE001
                    pass
            with self._events_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, default=str) + "\n")
            self.manifest.steps += 1
        except Exception:  # noqa: BLE001
            pass

    def record_error(self, step: int, message: str) -> None:
        """Record an error event (observe/parse/validation failure, etc.)."""
        try:
            if not self._started:
                self.start()
            event: dict[str, Any] = {
                "type": "error",
                "step": step,
                "t_offset_ms": round((time.monotonic() - self._started_mono) * 1000.0, 1),
                "timestamp": _iso_now(),
                "error": message,
            }
            with self._events_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, default=str) + "\n")
        except Exception:  # noqa: BLE001
            pass

    def update_meta(self, key: str, value: Any) -> None:
        with contextlib.suppress(Exception):  # noqa: BLE001
            self.manifest.metadata[key] = value

    def finish(self, success: bool, reason: str = "", summary: str = "") -> Path:
        """Write the final manifest. Safe to call multiple times."""
        try:
            if not self._started:
                self.start()
            self.manifest.success = success
            self.manifest.reason = reason
            self.manifest.summary = summary
            self.manifest.ended_at = _iso_now()
            self.manifest.duration_s = round(time.monotonic() - self._started_mono, 3)
            (self._dir / "manifest.json").write_text(
                json.dumps(self.manifest.to_dict(), indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            self._finished = True
        except Exception:  # noqa: BLE001
            pass
        return self._dir

    @property
    def finished(self) -> bool:
        return self._finished
