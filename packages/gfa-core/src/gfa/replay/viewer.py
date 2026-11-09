"""Replay viewer: load recorded sessions and scrub the timeline."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


class ReplayViewer:
    """Loads a recorded session and provides timeline access to its steps/frames."""

    def __init__(self, data_dir: Path, session_id: str | None = None, replay_dir: Path | None = None):
        if replay_dir is not None:
            self._dir = Path(replay_dir)
        elif session_id:
            self._dir = Path(data_dir) / "replays" / session_id
        else:
            raise ValueError("ReplayViewer requires session_id or replay_dir")
        self.session_id = self._dir.name
        self.manifest: dict[str, Any] = {}
        self.events: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        manifest_path = self._dir / "manifest.json"
        if manifest_path.exists():
            self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        events_path = self._dir / "events.jsonl"
        if events_path.exists():
            for line in events_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    self.events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    # ------------------------------------------------------------------
    @property
    def steps(self) -> list[dict[str, Any]]:
        return [e for e in self.events if e.get("type") == "step"]

    @property
    def errors(self) -> list[dict[str, Any]]:
        return [e for e in self.events if e.get("type") == "error"]

    def frame_path(self, step: int) -> Path | None:
        for ev in self.steps:
            if ev.get("step") == step and ev.get("frame"):
                p = self._dir / ev["frame"]
                return p if p.exists() else None
        return None

    def step_at(self, offset_ms: float) -> dict[str, Any] | None:
        """Return the step event nearest to (and not after) `offset_ms`."""
        best: dict[str, Any] | None = None
        for ev in self.steps:
            t = float(ev.get("t_offset_ms", 0.0))
            if t <= offset_ms and (best is None or t >= float(best.get("t_offset_ms", 0.0))):
                best = ev
        return best

    def timeline(self) -> list[tuple[float, int]]:
        """List of (t_offset_ms, step) for every recorded step — timeline scrubbing."""
        return [(float(e.get("t_offset_ms", 0.0)), int(e.get("step", 0))) for e in self.steps]

    def summary(self) -> str:
        """Human-readable summary of the whole replay."""
        m = self.manifest
        lines = [f"Replay {self.session_id}"]
        lines.append(f"  Game: {m.get('game') or '-'}  Model: {m.get('model') or '-'}")
        lines.append(f"  Objective: {m.get('objective') or '-'}")
        lines.append(f"  Started: {m.get('started_at', '-')}  Ended: {m.get('ended_at') or '-'}")
        lines.append(f"  Steps: {len(self.steps)}  Frames: {m.get('frames', 0)}  Duration: {m.get('duration_s', 0)}s")
        lines.append(f"  Result: {'SUCCESS' if m.get('success') else 'FAILED'} ({m.get('reason') or '-'})")
        if m.get("summary"):
            lines.append(f"  Summary: {m['summary']}")
        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")
        for ev in self.steps[:5]:
            r = (ev.get("reasoning") or "")[:60]
            lines.append(f"  step {ev.get('step')}: {r}")
        if len(self.steps) > 5:
            lines.append(f"  ... ({len(self.steps) - 5} more steps)")
        return "\n".join(lines)

    def export(self, dest: Path) -> Path:
        """Copy the whole replay directory to `dest` (e.g., for sharing/backup)."""
        dest = Path(dest)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(self._dir, dest)
        return dest


def list_replays(data_dir: Path) -> list[dict[str, Any]]:
    """List all recorded replays with their manifests."""
    base = Path(data_dir) / "replays"
    if not base.exists():
        return []
    out: list[dict[str, Any]] = []
    for d in sorted(base.iterdir(), key=lambda p: p.name, reverse=True):
        mp = d / "manifest.json"
        if mp.exists():
            try:
                out.append(json.loads(mp.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        else:
            out.append({"session_id": d.name, "status": "incomplete"})
    return out
