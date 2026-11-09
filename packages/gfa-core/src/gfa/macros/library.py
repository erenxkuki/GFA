"""Macro library: persistent store of named macros."""

from __future__ import annotations

import json
from pathlib import Path

from gfa.macros.models import Macro


class MacroLibraryError(Exception):
    pass


class MacroLibrary:
    """Stores named macros as JSON files under ``<data_dir>/macros/``.

    Names map 1:1 to files (``<name>.json``) so the directory doubles as the
    human-readable listing.
    """

    def __init__(self, data_dir: Path | None = None):
        if data_dir is None:
            from gfa.core.config import ConfigManager

            data_dir = ConfigManager().data_dir
        self.data_dir = Path(data_dir)
        self._dir = self.data_dir / "macros"

    @property
    def macro_dir(self) -> Path:
        return self._dir

    def _path(self, name: str) -> Path:
        if "/" in name or "\\" in name or ".." in name:
            raise MacroLibraryError(f"invalid macro name: {name!r}")
        return self._dir / f"{name}.json"

    def save(self, macro: Macro) -> Macro:
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path(macro.name).write_text(
            json.dumps(macro.to_dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return macro

    def load(self, name: str) -> Macro:
        p = self._path(name)
        if not p.exists():
            raise MacroLibraryError(f"macro not found: {name}")
        try:
            return Macro.from_dict(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise MacroLibraryError(f"invalid macro file '{name}': {exc}") from exc

    def exists(self, name: str) -> bool:
        return self._path(name).exists()

    def list(self) -> list[Macro]:
        if not self._dir.exists():
            return []
        out: list[Macro] = []
        for p in sorted(self._dir.glob("*.json")):
            try:
                out.append(Macro.from_dict(json.loads(p.read_text(encoding="utf-8"))))
            except (json.JSONDecodeError, TypeError):
                continue
        return out

    def delete(self, name: str) -> bool:
        p = self._path(name)
        if not p.exists():
            return False
        p.unlink()
        return True

    def export_json(self, name: str) -> str:
        return json.dumps(self.load(name).to_dict(), indent=2, ensure_ascii=False, default=str)

    def import_json(self, data: str | dict) -> Macro:
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as exc:
                raise MacroLibraryError(f"invalid macro JSON: {exc}") from exc
        if not isinstance(data, dict) or "name" not in data:
            raise MacroLibraryError("macro JSON must be an object with a 'name' field")
        return self.save(Macro.from_dict(data))
