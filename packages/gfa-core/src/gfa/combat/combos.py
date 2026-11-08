"""Combat combo system: predefined input sequences with precise timing."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from gfa.universal.sync_input import SyncInputController


@dataclass
class ComboStep:
    keys: list[str] = field(default_factory=list)  # keys to hold
    mouse_delta: tuple[int, int] = (0, 0)  # mouse movement
    click: str | None = None  # mouse button to click
    hold_ms: float = 50  # how long to hold
    delay_after: float = 0  # delay before next step


@dataclass
class Combo:
    name: str
    steps: list[ComboStep] = field(default_factory=list)
    description: str = ""
    cooldown_ms: float = 0  # minimum time between uses
    _last_used: float = 0.0

    def can_use(self) -> bool:
        return (time.time() - self._last_used) * 1000 >= self.cooldown_ms

    def execute(self, ctrl: SyncInputController) -> bool:
        if not self.can_use():
            return False
        self._last_used = time.time()
        for step in self.steps:
            # Mouse movement
            if step.mouse_delta != (0, 0):
                ctrl.move_mouse(step.mouse_delta[0], step.mouse_delta[1])
            # Key holds
            if step.keys:
                ctrl.hold_keys(step.keys)
            # Click
            if step.click:
                ctrl.click(step.click, hold_ms=step.hold_ms)
            else:
                time.sleep(step.hold_ms / 1000.0)
            # Release keys
            if step.keys and step.click is None:
                ctrl.release_keys(step.keys)
            if step.delay_after > 0:
                time.sleep(step.delay_after / 1000.0)
        return True


class ComboLibrary:
    """Library of predefined combos."""

    def __init__(self):
        self.combos: dict[str, Combo] = {}

    def register(self, combo: Combo) -> None:
        self.combos[combo.name] = combo

    def get(self, name: str) -> Combo | None:
        return self.combos.get(name)

    def execute(self, name: str, ctrl: SyncInputController) -> bool:
        combo = self.combos.get(name)
        if combo is None:
            return False
        return combo.execute(ctrl)

    def list_combos(self) -> list[str]:
        return list(self.combos.keys())


# ---- Preset combos ----

def dodge_left() -> Combo:
    return Combo(name="dodge_left", cooldown_ms=500, steps=[
        ComboStep(keys=["a"], hold_ms=100, delay_after=50),
    ])

def dodge_right() -> Combo:
    return Combo(name="dodge_right", cooldown_ms=500, steps=[
        ComboStep(keys=["d"], hold_ms=100, delay_after=50),
    ])

def dodge_back() -> Combo:
    return Combo(name="dodge_back", cooldown_ms=500, steps=[
        ComboStep(keys=["s"], hold_ms=100, delay_after=50),
    ])

def attack_combo_3hit() -> Combo:
    """3-hit combo: attack, attack, attack with timing."""
    return Combo(name="combo_3hit", cooldown_ms=1000, steps=[
        ComboStep(click="left", hold_ms=30, delay_after=200),
        ComboStep(click="left", hold_ms=30, delay_after=200),
        ComboStep(click="left", hold_ms=30, delay_after=100),
    ])

def parry_counter() -> Combo:
    """Parry then counter-attack."""
    return Combo(name="parry_counter", cooldown_ms=800, steps=[
        ComboStep(keys=["shift"], hold_ms=50, delay_after=100),  # block/parry
        ComboStep(click="left", hold_ms=30, delay_after=50),  # counter
    ])

def dash_attack() -> Combo:
    """Dash forward + attack."""
    return Combo(name="dash_attack", cooldown_ms=1200, steps=[
        ComboStep(keys=["w", "shift"], hold_ms=100, delay_after=50),  # dash
        ComboStep(click="left", hold_ms=30, delay_after=100),  # attack
    ])

def jump_attack() -> Combo:
    return Combo(name="jump_attack", cooldown_ms=800, steps=[
        ComboStep(keys=["space"], hold_ms=50, delay_after=100),  # jump
        ComboStep(click="left", hold_ms=30, delay_after=50),  # attack in air
    ])


def create_default_library() -> ComboLibrary:
    lib = ComboLibrary()
    for factory in [dodge_left, dodge_right, dodge_back, attack_combo_3hit,
                    parry_counter, dash_attack, jump_attack]:
        lib.register(factory())
    return lib