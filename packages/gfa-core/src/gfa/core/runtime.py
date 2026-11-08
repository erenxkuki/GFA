"""GFA core runtime lifecycle, state, and health checks."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from gfa.core.config import ConfigManager
from gfa.core.events import Event, EventBus
from gfa.core.logging import get_logger

log = get_logger("runtime")


class RuntimeState(StrEnum):
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class HealthReport:
    ok: bool
    state: str
    checks: dict[str, bool]
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class Runtime:
    """Owns application lifecycle, config, events, and high-level state."""

    def __init__(self, config: ConfigManager | None = None):
        self.config = config or ConfigManager()
        self.events = EventBus()
        self._state = RuntimeState.INITIALIZING
        self._started_at: float | None = None
        self._errors: list[str] = []
        self._components: dict[str, Any] = {}
        self.config.ensure_dirs()

    @property
    def state(self) -> RuntimeState:
        return self._state

    def register(self, name: str, component: Any) -> None:
        self._components[name] = component

    def get_component(self, name: str) -> Any:
        return self._components.get(name)

    def start(self) -> None:
        if self._state not in (RuntimeState.INITIALIZING, RuntimeState.STOPPED):
            return
        log.info("Starting GFA runtime")
        self._state = RuntimeState.INITIALIZING
        self._started_at = time.time()
        self._state = RuntimeState.READY
        self.events.emit(Event("runtime.started", {"state": self._state.value}))
        log.info("GFA runtime ready")

    def mark_running(self) -> None:
        self._state = RuntimeState.RUNNING

    def pause(self) -> None:
        if self._state == RuntimeState.RUNNING:
            self._state = RuntimeState.PAUSED
            self.events.emit(Event("runtime.paused"))

    def resume(self) -> None:
        if self._state == RuntimeState.PAUSED:
            self._state = RuntimeState.RUNNING
            self.events.emit(Event("runtime.resumed"))

    def stop(self) -> None:
        if self._state == RuntimeState.STOPPED:
            return
        log.info("Stopping GFA runtime")
        self._state = RuntimeState.STOPPING
        self.events.emit(Event("runtime.stopping"))
        self._state = RuntimeState.STOPPED
        self.events.emit(Event("runtime.stopped"))

    def record_error(self, message: str) -> None:
        self._errors.append(message)
        self._state = RuntimeState.ERROR
        log.error(message)

    def health(self) -> HealthReport:
        checks = {
            "config_loaded": self.config is not None,
            "data_dir_exists": self.config.data_dir.exists(),
            "event_bus": True,
        }
        ok = all(checks.values()) and self._state != RuntimeState.ERROR
        return HealthReport(
            ok=ok,
            state=self._state.value,
            checks=checks,
            details={
                "started_at": self._started_at,
                "uptime_seconds": (time.time() - self._started_at) if self._started_at else 0,
                "errors": list(self._errors[-10:]),
                "components": sorted(self._components.keys()),
            },
        )

    def diagnostics(self) -> dict[str, Any]:
        return {
            "version": __import__("gfa").__version__,
            "state": self._state.value,
            "config_path": str(self.config.path),
            "data_dir": str(self.config.data_dir),
            "health": self.health().__dict__,
        }