"""Game profiles: registry of known games with detection hints + presets.

A :class:`GameProfile` describes one game: title/process keywords for
detection plus the keybind preset and optional adapter to load when the game
is detected. Profiles persist as JSON in ``<data_dir>/games/profiles.json``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from gfa.detection.windows import ForegroundWindow


@dataclass
class GameProfile:
    """One known game: how to detect it and what to load when detected."""

    game_id: str
    name: str = ""
    genre: str | None = None  # fps | rpg | platformer | racing | strategy
    title_keywords: list[str] = field(default_factory=list)
    process_keywords: list[str] = field(default_factory=list)
    keybind_preset: str | None = None  # e.g. "fps_wasd"
    adapter_id: str | None = None
    match_threshold: float = 0.5

    def __post_init__(self):
        if not self.name:
            self.name = self.game_id

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameProfile:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def score(self, window: ForegroundWindow | None) -> float:
        """Match score in [0, 1] for a window (0 = no evidence)."""
        if window is None:
            return 0.0
        score = 0.0
        title = (window.title or "").lower()
        proc = (window.process_name or "").lower()
        title_hits = sum(1 for kw in self.title_keywords if kw.lower() in title)
        proc_hits = sum(1 for kw in self.process_keywords if kw.lower() in proc)
        if title_hits:
            score += min(0.6, 0.3 * title_hits)
        if proc_hits:
            score += min(0.45, 0.3 * proc_hits)
        if title and title.strip().lower() == self.game_id.lower():
            score += 0.2  # exact title match
        return round(min(1.0, score), 3)


def default_profiles() -> list[GameProfile]:
    """Built-in profiles for common games (title/process hints + key binds)."""
    return [
        GameProfile(game_id="minecraft", name="Minecraft", genre="fps",
                    title_keywords=["minecraft"], process_keywords=["javaw.exe", "minecraft"],
                    keybind_preset="fps-wasd"),
        GameProfile(game_id="roblox", name="Roblox", genre="platformer",
                    title_keywords=["roblox"], process_keywords=["robloxplayerbeta.exe", "roblox"],
                    keybind_preset="fps-wasd"),
        GameProfile(game_id="zzz", name="Zenless Zone Zero", genre="fps",
                    title_keywords=["zenless", "zzz"], process_keywords=["zzz.exe", "zenless"],
                    keybind_preset="fps-wasd"),
        GameProfile(game_id="eldenring", name="Elden Ring", genre="rpg",
                    title_keywords=["elden ring"], process_keywords=["eldenring.exe"],
                    keybind_preset="fps-arrows"),
    ]


class GameProfileRegistry:
    """Persistent registry of game profiles.

    Seeds itself with :func:`default_profiles` on first use (unless the store
    already exists), so detection works out of the box.
    """

    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            from gfa.core.config import ConfigManager

            data_dir = ConfigManager().data_dir
        self.data_dir = Path(data_dir)
        self._path = self.data_dir / "games" / "profiles.json"
        self._profiles: dict[str, GameProfile] = {}
        self._load_or_seed()

    # ------------------------------------------------------------------
    def _load_or_seed(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for item in data:
                    p = GameProfile.from_dict(item)
                    self._profiles[p.game_id] = p
                return
            except (json.JSONDecodeError, TypeError):
                pass
        for p in default_profiles():
            self._profiles[p.game_id] = p
        self._persist()

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([p.to_dict() for p in self._profiles.values()], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    def register(self, profile: GameProfile) -> GameProfile:
        self._profiles[profile.game_id] = profile
        self._persist()
        return profile

    def remove(self, game_id: str) -> bool:
        if game_id not in self._profiles:
            return False
        del self._profiles[game_id]
        self._persist()
        return True

    def get(self, game_id: str) -> GameProfile | None:
        return self._profiles.get(game_id)

    def list(self) -> list[GameProfile]:
        return sorted(self._profiles.values(), key=lambda p: p.game_id)

    # ------------------------------------------------------------------
    def match(self, window: ForegroundWindow | None) -> list[tuple[GameProfile, float]]:
        """All profiles scoring at/above their threshold, best first."""
        scored = [(p, p.score(window)) for p in self._profiles.values()]
        matches = [(p, s) for p, s in scored if s >= p.match_threshold]
        matches.sort(key=lambda t: -t[1])
        return matches

    def best(self, window: ForegroundWindow | None) -> tuple[GameProfile, float] | None:
        matches = self.match(window)
        return matches[0] if matches else None
