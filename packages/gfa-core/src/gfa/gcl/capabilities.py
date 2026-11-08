"""Capability system for GCL."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CapabilitySet:
    capabilities: set[str] = field(default_factory=set)

    def add(self, cap: str) -> None:
        self.capabilities.add(cap)

    def add_many(self, caps: list[str] | set[str]) -> None:
        self.capabilities.update(caps)

    def has(self, cap: str) -> bool:
        return cap in self.capabilities

    def remove(self, cap: str) -> None:
        self.capabilities.discard(cap)

    @staticmethod
    def core_capabilities() -> CapabilitySet:
        cs = CapabilitySet()
        # every core command type is a capability "gcl.<type>"
        from gfa.gcl.commands import default_registry
        for ctype in default_registry().all():
            cs.add(f"gcl.{ctype}")
        # universal baseline capabilities
        cs.add("universal.screen_capture")
        cs.add("universal.keyboard")
        cs.add("universal.mouse")
        return cs

    def allows_command(self, ctype: str) -> bool:
        if f"gcl.{ctype}" in self.capabilities:
            return True
        # extensions: command type invoke requires capability named in params (checked separately)
        if ctype == "invoke":
            return True
        return ctype == "action"