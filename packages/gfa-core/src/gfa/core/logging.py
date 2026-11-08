"""Structured logging helpers for GFA."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_LOGGERS: dict[str, logging.Logger] = {}


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    root = logging.getLogger("gfa")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)
    root.addHandler(console)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    if name not in _LOGGERS:
        _LOGGERS[name] = logging.getLogger(f"gfa.{name}")
    return _LOGGERS[name]