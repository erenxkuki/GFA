"""Adapter manifest schema and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError


class AdapterManifest(BaseModel):
    manifest_version: str = "1"
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    description: str = ""
    author: str = ""
    license: str = "MIT"
    gfa_compatibility: str = ">=0.1.0"
    gcl_compatibility: str = "gcl-v1"
    capabilities: list[str] = Field(default_factory=list)
    repository: str | None = None
    entrypoint: str = Field(..., min_length=1)
    permissions: list[str] = Field(default_factory=list)
    homepage: str | None = None

    @classmethod
    def from_file(cls, path: Path) -> "AdapterManifest":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**data)

    def to_file(self, path: Path) -> None:
        path.write_text(json.dumps(self.model_dump(), indent=2), encoding="utf-8")


def validate_manifest_file(path: Path) -> tuple[bool, list[str], AdapterManifest | None]:
    errors: list[str] = []
    try:
        manifest = AdapterManifest.from_file(path)
    except (json.JSONDecodeError, ValidationError, OSError) as exc:
        return False, [str(exc)], None
    # additional checks
    if not manifest.id.replace(".", "").replace("-", "").replace("_", "").isalnum():
        errors.append("id must be alphanumeric with . - _")
    if errors:
        return False, errors, None
    return True, [], manifest