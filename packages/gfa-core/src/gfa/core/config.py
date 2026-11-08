"""Configuration management for GFA."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from gfa.shared.errors import ConfigurationError


def default_data_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        root = Path(base) if base else Path.home() / "AppData" / "Roaming"
    elif os.name == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return root / "GFA"


def default_config_path() -> Path:
    return default_data_dir() / "config.json"


class ConfigManager:
    """Loads, validates, and persists GFA configuration as JSON."""

    def __init__(self, path: Path | None = None):
        self.path = path or default_config_path()
        self._data: dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ConfigurationError(f"Failed to load config: {exc}") from exc
        else:
            self._data = self._default()

    def _default(self) -> dict[str, Any]:
        return {
            "version": 1,
            "data_dir": str(default_data_dir()),
            "log_level": "INFO",
            "models": [],
            "active_model": None,
            "session": {"max_observation_fps": 2, "screenshot_scale": 0.5},
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        cur: Any = self._data
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur

    def set(self, key: str, value: Any) -> None:
        parts = key.split(".")
        cur = self._data
        for part in parts[:-1]:
            if part not in cur or not isinstance(cur[part], dict):
                cur[part] = {}
            cur = cur[part]
        cur[parts[-1]] = value

    def all(self) -> dict[str, Any]:
        return dict(self._data)

    @property
    def data_dir(self) -> Path:
        return Path(self.get("data_dir", str(default_data_dir())))

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "logs").mkdir(exist_ok=True)
        (self.data_dir / "sessions").mkdir(exist_ok=True)
        (self.data_dir / "memory").mkdir(exist_ok=True)