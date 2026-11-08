"""Registry database helpers."""

import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS adapters (
    id TEXT PRIMARY KEY,
    name TEXT,
    description TEXT,
    author TEXT,
    repository TEXT,
    homepage TEXT,
    license TEXT,
    status TEXT DEFAULT 'pending',
    owner_token TEXT,
    created_at TEXT,
    updated_at TEXT,
    metadata TEXT
);
CREATE TABLE IF NOT EXISTS releases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adapter_id TEXT,
    version TEXT,
    gfa_compatibility TEXT,
    gcl_compatibility TEXT,
    capabilities TEXT,
    checksum TEXT,
    artifact_url TEXT,
    created_at TEXT,
    FOREIGN KEY(adapter_id) REFERENCES adapters(id)
);
CREATE TABLE IF NOT EXISTS verification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adapter_id TEXT,
    release_version TEXT,
    check_name TEXT,
    passed INTEGER,
    details TEXT,
    created_at TEXT
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def row_to_dict(row) -> dict[str, Any]:
    if row is None:
        return {}
    d = dict(row)
    for k in ("metadata", "capabilities"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except json.JSONDecodeError:
                pass
    return d