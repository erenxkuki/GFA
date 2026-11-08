"""In-process event bus for GFA."""

from __future__ import annotations

import contextlib
import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

EventHandler = Callable[["Event"], None]


@dataclass
class Event:
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str | None = None


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event_name: str, handler: EventHandler) -> Callable[[], None]:
        with self._lock:
            self._handlers[event_name].append(handler)

        def unsubscribe() -> None:
            with self._lock, contextlib.suppress(ValueError):
                self._handlers[event_name].remove(handler)

        return unsubscribe

    def emit(self, event: Event) -> None:
        with self._lock:
            handlers = list(self._handlers.get(event.name, []))
            wildcard = list(self._handlers.get("*", []))
        for h in handlers + wildcard:
            with contextlib.suppress(Exception):
                h(event)

    def handler_count(self, event_name: str) -> int:
        with self._lock:
            return len(self._handlers.get(event_name, []))