"""Diagnostics helpers for `gfa doctor`."""

from __future__ import annotations

import platform
import sys
from typing import Any

from gfa import __version__
from gfa.core.config import ConfigManager
from gfa.core.runtime import Runtime


def run_doctor(config: ConfigManager | None = None, runtime: Runtime | None = None) -> dict[str, Any]:
    config = config or ConfigManager()
    runtime = runtime or Runtime(config)
    runtime.start()
    health = runtime.health()
    checks: dict[str, Any] = {
        "gfa_version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "config_path": str(config.path),
        "config_exists": config.path.exists(),
        "data_dir": str(config.data_dir),
        "data_dir_exists": config.data_dir.exists(),
        "health_ok": health.ok,
        "health_state": health.state,
    }
    # Optional dependency checks
    optional = {}
    for mod in ("httpx", "pydantic", "typer", "rich", "sqlalchemy", "cryptography", "fastapi"):
        try:
            m = __import__(mod)
            optional[mod] = getattr(m, "__version__", "installed")
        except Exception:  # noqa: BLE001
            optional[mod] = None
    checks["optional_dependencies"] = optional
    # keyring
    try:
        import keyring  # noqa: F401

        checks["keyring"] = "available"
    except Exception:  # noqa: BLE001
        checks["keyring"] = "not available (encrypted fallback in use)"
    return checks