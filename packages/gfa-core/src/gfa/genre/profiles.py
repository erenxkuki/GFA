"""Genre profiles: per-genre UI elements a perception model should look for.

Each :class:`GenreProfile` lists the HUD elements typical of a genre
(crosshair/health/ammo for FPS, dialogue/quest/inventory for RPG, ...).
The :class:`gfa.genre.detectors.GenreDetector` runs specialized detectors
for these elements over frame pixels — much cheaper and more precise than
asking a general vision model to find them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ElementConfig:
    """One genre's UI element: name + kind (detector dispatch) + region hint."""

    name: str           # e.g. "health_bar"
    kind: str           # crosshair | bar | dialogue | marker | minimap | digits | grid | panel
    region: str = "center"  # center|top_left|top_right|bottom_left|bottom_right|top_band|bottom_band|right_band


@dataclass
class GenreProfile:
    name: str           # "fps" | "rpg" | "platformer" | "racing" | "strategy"
    elements: list[ElementConfig] = field(default_factory=list)
    description: str = ""

    def __post_init__(self):
        if not self.description:
            self.description = f"{self.name} HUD elements"


def fps_profile() -> GenreProfile:
    return GenreProfile(name="fps", description="First-person shooter HUD", elements=[
        ElementConfig("crosshair", "crosshair", "center"),
        ElementConfig("health_bar", "bar", "top_left"),
        ElementConfig("ammo", "digits", "bottom_right"),
        ElementConfig("scoreboard", "digits", "top_band"),
        ElementConfig("hitmarker", "crosshair", "center"),
    ])


def rpg_profile() -> GenreProfile:
    return GenreProfile(name="rpg", description="RPG HUD", elements=[
        ElementConfig("dialogue_box", "dialogue", "bottom_band"),
        ElementConfig("quest_marker", "marker", "top_right"),
        ElementConfig("health_bar", "bar", "top_left"),
        ElementConfig("inventory", "grid", "bottom_right"),
        ElementConfig("location_label", "digits", "top_band"),
    ])


def platformer_profile() -> GenreProfile:
    return GenreProfile(name="platformer", description="Platformer HUD", elements=[
        ElementConfig("health_bar", "bar", "top_left"),
        ElementConfig("score", "digits", "top_band"),
        ElementConfig("collectibles", "marker", "top_right"),
        ElementConfig("progress", "bar", "top_band"),
    ])


def racing_profile() -> GenreProfile:
    return GenreProfile(name="racing", description="Racing HUD", elements=[
        ElementConfig("speedometer", "digits", "bottom_band"),
        ElementConfig("lap_counter", "digits", "top_band"),
        ElementConfig("position", "digits", "top_right"),
        ElementConfig("minimap", "minimap", "top_left"),
    ])


def strategy_profile() -> GenreProfile:
    return GenreProfile(name="strategy", description="Strategy HUD", elements=[
        ElementConfig("minimap", "minimap", "top_right"),
        ElementConfig("resource_bar", "panel", "top_band"),
        ElementConfig("unit_selection", "digits", "bottom_left"),
        ElementConfig("menu_bar", "panel", "right_band"),
        ElementConfig("health_bar", "bar", "top_left"),
    ])


GENRE_PROFILES: dict[str, GenreProfile] = {
    p.name: p for p in [fps_profile(), rpg_profile(), platformer_profile(),
                        racing_profile(), strategy_profile()]
}


def get_genre(name: str) -> GenreProfile:
    key = (name or "").strip().lower()
    if key not in GENRE_PROFILES:
        raise ValueError(f"unknown genre '{name}'; expected one of {sorted(GENRE_PROFILES)}")
    return GENRE_PROFILES[key]


def list_genres() -> list[str]:
    return sorted(GENRE_PROFILES.keys())


# Keyword hints for selecting a genre from free text / titles
_GENRE_KEYWORDS: dict[str, list[str]] = {
    "fps": ["shooter", "fps", "first-person", "first person"],
    "rpg": ["rpg", "role-playing", "role playing", "quest", "adventure"],
    "platformer": ["platformer", "platform", "mario", "celeste"],
    "racing": ["racing", "race", "drive", "driving"],
    "strategy": ["strategy", "tactic", "indsrpg", "grand strategy"],
}


def select_genre_for_keywords(keywords: list[str]) -> str | None:
    """Pick a genre from keyword hints (first match wins), else None."""
    text = " ".join(keywords).lower()
    for genre, hints in _GENRE_KEYWORDS.items():
        if any(h in text for h in hints):
            return genre
    return None
