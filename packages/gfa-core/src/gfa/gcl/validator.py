"""GCL validator."""

from __future__ import annotations

from dataclasses import dataclass

from gfa.gcl.capabilities import CapabilitySet
from gfa.gcl.commands import default_registry, validate_field_types
from gfa.gcl.schema import Command, CommandBatch, ValidationResult


@dataclass
class ValidationContext:
    capabilities: CapabilitySet
    max_commands_per_batch: int = 64
    max_total_duration_ms: int = 60000
    allowed_command_types: set[str] | None = None  # optional allowlist override


class GCLValidator:
    def __init__(self, registry=None):
        self.registry = registry or default_registry()

    def validate_batch(self, batch: CommandBatch, context: ValidationContext) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        if len(batch.commands) > context.max_commands_per_batch:
            errors.append(f"Too many commands: {len(batch.commands)} > {context.max_commands_per_batch}")
        # duplicate id detection
        ids = [c.id for c in batch.commands if c.id]
        if len(ids) != len(set(ids)):
            errors.append("Duplicate command ids in batch")
        total_dur = 0
        for idx, cmd in enumerate(batch.commands):
            # type known?
            spec = self.registry.get(cmd.type)
            if spec is None:
                # allow extension/invoke and action always via registry already; unknown -> reject
                errors.append(f"command[{idx}]: unknown type '{cmd.type}'")
                continue
            if context.allowed_command_types is not None and cmd.type not in context.allowed_command_types:
                errors.append(f"command[{idx}]: type '{cmd.type}' not allowed in this context")
                continue
            # capability check
            if not context.capabilities.allows_command(cmd.type):
                errors.append(f"command[{idx}]: capability missing for '{cmd.type}'")
                continue
            if cmd.type == "invoke":
                cap = cmd.params.get("capability")
                if not isinstance(cap, str) or not context.capabilities.has(cap):
                    errors.append(f"command[{idx}]: invoke capability not granted: {cap}")
                    continue
            # field validation
            field_errors = validate_field_types(spec, cmd.params)
            for fe in field_errors:
                errors.append(f"command[{idx}] ({cmd.type}): {fe}")
            # duration accounting
            dur = cmd.params.get("duration_ms")
            if isinstance(dur, int):
                total_dur += dur
        if total_dur > context.max_total_duration_ms:
            errors.append(f"Total duration {total_dur}ms exceeds budget {context.max_total_duration_ms}ms")
        return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)

    def validate_command(self, cmd: Command, context: ValidationContext) -> ValidationResult:
        batch = CommandBatch(protocol="gcl-v1", commands=[cmd])
        return self.validate_batch(batch, context)