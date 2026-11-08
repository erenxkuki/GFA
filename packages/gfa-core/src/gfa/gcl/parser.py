"""GCL parser."""

from __future__ import annotations

import json
from typing import Any

from gfa.gcl.schema import Command, CommandBatch
from gfa.shared.errors import ValidationError

KNOWN_TOP_LEVEL_FIELDS = {
    "id", "type", "scope", "target", "direction", "duration_ms", "speed",
    "x", "y", "dx", "dy", "relative", "button", "count", "amount", "key", "action", "axis", "value", "text", "name", "params", "capability",
    "expected_result", "region",
}
META_FIELDS = {"protocol", "commands", "metadata", "version"}


def _normalize_command(raw: dict[str, Any]) -> Command:
    if not isinstance(raw, dict):
        raise ValidationError("Command must be an object", code="invalid_command")
    if "type" not in raw:
        raise ValidationError("Command missing 'type'", code="missing_type")
    ctype = raw["type"]
    if not isinstance(ctype, str):
        raise ValidationError("'type' must be a string", code="invalid_type")
    cid = raw.get("id")
    if cid is not None and not isinstance(cid, str):
        cid = str(cid)
    # params: explicit params dict takes precedence; merge other top-level fields
    params = dict(raw.get("params") or {})
    for k, v in raw.items():
        if k in META_FIELDS or k in ("type", "id", "params"):
            continue
        if k not in params:
            params[k] = v
    return Command(type=ctype, id=cid, params=params, raw=dict(raw))


def parse_batch(data: Any) -> CommandBatch:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON: {exc}", code="invalid_json") from exc
    if isinstance(data, list):
        data = {"protocol": "gcl-v1", "commands": data}
    if not isinstance(data, dict):
        raise ValidationError("GCL batch must be an object or list", code="invalid_batch")
    protocol = data.get("protocol") or data.get("version") or "gcl-v1"
    if protocol != "gcl-v1":
        raise ValidationError(f"Unsupported protocol: {protocol}", code="unsupported_protocol")
    cmds_raw = data.get("commands")
    if not isinstance(cmds_raw, list):
        raise ValidationError("'commands' must be a list", code="invalid_commands")
    if len(cmds_raw) == 0:
        raise ValidationError("Empty command list", code="empty_commands")
    commands = [_normalize_command(c) for c in cmds_raw]
    metadata = data.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return CommandBatch(protocol=protocol, commands=commands, metadata=metadata)


def parse_single(data: Any) -> Command:
    batch = parse_batch({"protocol": "gcl-v1", "commands": [data] if not isinstance(data, dict) or "commands" not in data else data["commands"]})
    # if data is a single command dict without commands, handle:
    if isinstance(data, dict) and "type" in data and "commands" not in data:
        return _normalize_command(data)
    return batch.commands[0]