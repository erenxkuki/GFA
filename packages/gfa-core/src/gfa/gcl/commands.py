"""GCL command specifications and registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

DIRECTIONS = {"forward", "backward", "left", "right", "up", "down"}
MOUSE_BUTTONS = {"left", "right", "middle"}
KEY_ACTIONS = {"press", "release", "tap"}
SCOPES = {"screen", "window", "environment", "ui", "self"}


@dataclass
class CommandSpec:
    type: str
    category: str
    required: list[str] = field(default_factory=list)
    optional: list[str] = field(default_factory=list)
    field_types: dict[str, type | tuple] = field(default_factory=dict)
    max_duration_ms: int | None = None
    description: str = ""
    validator: Callable[[dict[str, Any]], list[str]] | None = None


class CommandRegistry:
    def __init__(self):
        self._specs: dict[str, CommandSpec] = {}
        self._register_defaults()

    def register(self, spec: CommandSpec) -> None:
        self._specs[spec.type] = spec

    def get(self, ctype: str) -> CommandSpec | None:
        return self._specs.get(ctype)

    def all(self) -> dict[str, CommandSpec]:
        return dict(self._specs)

    def _register_defaults(self):
        def add(**kw):
            self.register(CommandSpec(**kw))

        # Observation
        add(type="observe", category="observation", optional=["scope", "target"],
            field_types={"scope": str}, description="Capture/refresh observation.")
        add(type="observe_region", category="observation", required=["region"],
            optional=["scope"], field_types={"region": dict})
        # Movement
        add(type="move", category="movement", required=["direction"],
            optional=["duration_ms", "speed"],
            field_types={"direction": str, "duration_ms": int, "speed": (int, float)},
            max_duration_ms=5000)
        add(type="stop_movement", category="movement")
        # Mouse
        add(type="mouse_move", category="mouse", optional=["x", "y", "dx", "dy", "relative"],
            field_types={"x": int, "y": int, "dx": int, "dy": int, "relative": bool})
        add(type="click", category="mouse", optional=["button", "x", "y", "count"],
            field_types={"button": str, "x": int, "y": int, "count": int})
        add(type="scroll", category="mouse", optional=["amount", "direction"],
            field_types={"amount": int, "direction": str})
        # Keyboard
        add(type="key", category="keyboard", required=["key"],
            optional=["action"], field_types={"key": str, "action": str})
        add(type="type_text", category="keyboard", required=["text"],
            field_types={"text": str}, max_duration_ms=10000)
        # Controller
        add(type="controller_button", category="controller", required=["button"],
            optional=["action"], field_types={"button": str, "action": str})
        add(type="controller_axis", category="controller", required=["axis", "value"],
            field_types={"axis": str, "value": (int, float)})
        # Interaction
        add(type="interact", category="interaction", optional=["target", "action"],
            field_types={"target": str, "action": str})
        add(type="wait", category="wait", optional=["duration_ms"],
            field_types={"duration_ms": int}, max_duration_ms=30000)
        # Verification
        add(type="verify", category="verification", optional=["expected_result", "target"],
            field_types={"expected_result": str, "target": str})
        # Session
        add(type="session_pause", category="session")
        add(type="session_resume", category="session")
        add(type="session_stop", category="session")
        add(type="emergency_stop", category="session")
        # Game-specific extension invocation
        add(type="invoke", category="extension", required=["capability"],
            optional=["params"], field_types={"capability": str, "params": dict})
        # Generic action (adapter-defined) - kept for compatibility
        add(type="action", category="game_specific", required=["name"],
            optional=["params"], field_types={"name": str, "params": dict})


_DEFAULT_REGISTRY: CommandRegistry | None = None


def default_registry() -> CommandRegistry:
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = CommandRegistry()
    return _DEFAULT_REGISTRY


def validate_field_types(spec: CommandSpec, params: dict[str, Any]) -> list[str]:
    errors = []
    for field_name, expected in spec.field_types.items():
        if field_name not in params:
            continue
        val = params[field_name]
        if isinstance(expected, tuple):
            if not isinstance(val, expected):
                errors.append(f"field '{field_name}' expected {expected}, got {type(val).__name__}")
        else:
            if not isinstance(val, expected):
                errors.append(f"field '{field_name}' expected {expected.__name__}, got {type(val).__name__}")
    # required
    for r in spec.required:
        if r not in params:
            errors.append(f"missing required field '{r}'")
    CONTROL_FIELDS = {"timeout", "timeout_ms", "priority", "metadata"}
    # unknown fields
    allowed = set(spec.required) | set(spec.optional) | set(spec.field_types.keys()) | CONTROL_FIELDS
    for k in params:
        if k not in allowed:
            errors.append(f"unknown field '{k}' for command '{spec.type}'")
    # duration limit
    for dur_field in ("duration_ms",):
        if dur_field in params and isinstance(params[dur_field], int):
            if spec.max_duration_ms is not None and params[dur_field] > spec.max_duration_ms:
                errors.append(f"'{dur_field}' exceeds max {spec.max_duration_ms}ms")
            if params[dur_field] < 0:
                errors.append(f"'{dur_field}' must be non-negative")
    # semantic checks
    if spec.type == "move" and "direction" in params and params["direction"] not in DIRECTIONS:
        errors.append(f"invalid direction '{params['direction']}'")
    if spec.type == "click" and "button" in params and params["button"] not in MOUSE_BUTTONS:
        errors.append(f"invalid button '{params['button']}'")
    if spec.type == "key" and "action" in params and params["action"] not in KEY_ACTIONS:
        errors.append(f"invalid key action '{params['action']}'")
    if spec.type == "observe" and "scope" in params and params["scope"] not in SCOPES:
        errors.append(f"invalid scope '{params['scope']}'")
    if spec.type == "mouse_move":
        has_abs = "x" in params or "y" in params
        has_rel = "dx" in params or "dy" in params
        if not has_abs and not has_rel:
            errors.append("mouse_move requires x/y or dx/dy")
    if spec.validator:
        errors.extend(spec.validator(params))
    return errors