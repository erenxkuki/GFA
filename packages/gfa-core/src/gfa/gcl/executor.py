"""GCL execution runtime."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from gfa.gcl.schema import Command, CommandBatch, CommandResult, CommandStatus
from gfa.gcl.validator import GCLValidator, ValidationContext

Handler = Callable[[Command], Awaitable[dict[str, Any]]]


class CommandExecutor:
    """Executes validated GCL commands via registered handlers."""

    def __init__(self, validator: GCLValidator | None = None):
        self.validator = validator or GCLValidator()
        self._handlers: dict[str, Handler] = {}
        self._cancelled = False
        self._emergency = False
        self.results: list[CommandResult] = []

    def register_handler(self, ctype: str, handler: Handler) -> None:
        self._handlers[ctype] = handler

    def cancel(self) -> None:
        self._cancelled = True

    def emergency_stop(self) -> None:
        self._emergency = True
        self._cancelled = True

    def reset(self) -> None:
        self._cancelled = False
        self._emergency = False

    async def execute_batch(self, batch: CommandBatch, context: ValidationContext) -> list[CommandResult]:
        self.reset()
        vr = self.validator.validate_batch(batch, context)
        if not vr.ok:
            out = []
            for cmd in batch.commands:
                out.append(CommandResult(command_id=cmd.id, type=cmd.type, status=CommandStatus.REJECTED,
                                        message="; ".join(vr.errors)))
            self.results = out
            return out
        out: list[CommandResult] = []
        for cmd in batch.commands:
            if self._cancelled or self._emergency:
                res = CommandResult(command_id=cmd.id, type=cmd.type, status=CommandStatus.CANCELLED,
                                    message="Cancelled")
                out.append(res)
                continue
            handler = self._handlers.get(cmd.type)
            # extension invoke: handler keyed by capability? fall back to 'invoke'
            if handler is None and cmd.type == "invoke":
                handler = self._handlers.get(cmd.params.get("capability"))
            start = time.monotonic()
            started_iso = datetime.now(UTC).isoformat()
            try:
                if handler is None:
                    raise RuntimeError(f"No handler registered for '{cmd.type}'")
                # per-command timeout
                timeout = cmd.params.get("timeout_ms")
                if not isinstance(timeout, (int, float)):
                    timeout = 10000
                data = await asyncio.wait_for(handler(cmd), timeout=timeout / 1000.0)
                dur = (time.monotonic() - start) * 1000
                res = CommandResult(command_id=cmd.id, type=cmd.type, status=CommandStatus.SUCCEEDED,
                                    message="OK", data=data or {}, started_at=started_iso,
                                    ended_at=datetime.now(UTC).isoformat(),
                                    duration_ms=dur)
            except TimeoutError:
                dur = (time.monotonic() - start) * 1000
                res = CommandResult(command_id=cmd.id, type=cmd.type, status=CommandStatus.TIMED_OUT,
                                    message="Timed out", started_at=started_iso, duration_ms=dur)
            except Exception as exc:  # noqa: BLE001
                dur = (time.monotonic() - start) * 1000
                res = CommandResult(command_id=cmd.id, type=cmd.type, status=CommandStatus.FAILED,
                                    message=str(exc), started_at=started_iso, duration_ms=dur)
            out.append(res)
        self.results = out
        return out