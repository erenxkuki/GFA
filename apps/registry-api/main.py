"""Registry API (FastAPI)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "gfa-core" / "src"))
from gfa.adapter_sdk.manifest import AdapterManifest, validate_manifest_file

from database import connect, row_to_dict

DB_PATH = Path(__file__).parent / "registry.db"
app = FastAPI(title="GFA Registry API", version="0.1.0")


def get_conn():
    return connect(DB_PATH)


class SubmitAdapterRequest(BaseModel):
    repository: str
    owner_token: str | None = None
    manifest: dict[str, Any] | None = None  # optional inline manifest


class ReleaseRequest(BaseModel):
    version: str
    gfa_compatibility: str = ">=0.1.0"
    gcl_compatibility: str = "gcl-v1"
    capabilities: list[str] = []
    checksum: str | None = None
    artifact_url: str | None = None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def verify_manifest(manifest: AdapterManifest) -> list[dict[str, Any]]:
    checks = []
    checks.append({"check_name": "manifest_schema", "passed": True, "details": "ok"})
    # gfa compat
    checks.append({"check_name": "gfa_compat", "passed": manifest.gfa_compatibility.startswith(">="), "details": manifest.gfa_compatibility})
    # gcl compat
    checks.append({"check_name": "gcl_compat", "passed": manifest.gcl_compatibility == "gcl-v1", "details": manifest.gcl_compatibility})
    # id format
    checks.append({"check_name": "id_format", "passed": "." in manifest.id, "details": manifest.id})
    return checks


@app.get("/health")
def health():
    return {"status": "ok", "time": now()}


@app.post("/adapters/submit")
def submit_adapter(req: SubmitAdapterRequest):
    conn = get_conn()
    # resolve manifest
    manifest_obj = None
    if req.manifest:
        try:
            manifest_obj = AdapterManifest(**req.manifest)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=f"invalid manifest: {exc}")
    else:
        # try to read from repository if local path
        repo_path = Path(req.repository)
        if repo_path.exists() and (repo_path / "manifest.json").exists():
            ok, errors, manifest_obj = validate_manifest_file(repo_path / "manifest.json")
            if not ok:
                raise HTTPException(status_code=400, detail={"errors": errors})
        else:
            raise HTTPException(status_code=400, detail="manifest required or local repository path")

    adapter_id = manifest_obj.id
    # upsert adapter
    existing = conn.execute("SELECT id FROM adapters WHERE id=?", (adapter_id,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE adapters SET name=?,description=?,author=?,repository=?,homepage=?,license=?,owner_token=?,updated_at=?,metadata=? WHERE id=?",
            (manifest_obj.name, manifest_obj.description, manifest_obj.author, req.repository,
             manifest_obj.homepage, manifest_obj.license, req.owner_token, now(), json.dumps(manifest_obj.model_dump())),
            adapter_id)
    else:
        conn.execute(
            "INSERT INTO adapters (id,name,description,author,repository,homepage,license,status,owner_token,created_at,updated_at,metadata) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (adapter_id, manifest_obj.name, manifest_obj.description, manifest_obj.author, req.repository,
             manifest_obj.homepage, manifest_obj.license, "pending", req.owner_token, now(), now(), json.dumps(manifest_obj.model_dump())))
    conn.commit()

    # verification
    checks = verify_manifest(manifest_obj)
    for c in checks:
        conn.execute(
            "INSERT INTO verification (adapter_id,release_version,check_name,passed,details,created_at) VALUES (?,?,?,?,?,?)",
            (adapter_id, None, c["check_name"], 1 if c["passed"] else 0, c["details"], now()))
    conn.commit()

    # auto-approve if all checks pass
    if all(c["passed"] for c in checks):
        conn.execute("UPDATE adapters SET status='approved' WHERE id=?", (adapter_id,))
        conn.commit()

    return {"adapter_id": adapter_id, "status": "approved" if all(c["passed"] for c in checks) else "pending",
            "checks": checks}


@app.get("/adapters")
def list_adapters(
    q: str | None = None,
    status: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    conn = get_conn()
    where = []
    params: list[Any] = []
    if q:
        where.append("(name LIKE ? OR description LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    if status:
        where.append("status=?")
        params.append(status)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM adapters {clause}", params).fetchone()[0]
    rows = conn.execute(f"SELECT * FROM adapters {clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                        params + [limit, offset]).fetchall()
    items = [row_to_dict(r) for r in rows]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@app.get("/adapters/{adapter_id}")
def get_adapter(adapter_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM adapters WHERE id=?", (adapter_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    adapter = row_to_dict(row)
    releases = conn.execute("SELECT * FROM releases WHERE adapter_id=? ORDER BY id DESC", (adapter_id,)).fetchall()
    adapter["releases"] = [row_to_dict(r) for r in releases]
    verifs = conn.execute("SELECT * FROM verification WHERE adapter_id=? ORDER BY id DESC", (adapter_id,)).fetchall()
    adapter["verification"] = [row_to_dict(r) for r in verifs]
    return adapter


@app.post("/adapters/{adapter_id}/releases")
def add_release(adapter_id: str, req: ReleaseRequest):
    conn = get_conn()
    row = conn.execute("SELECT id FROM adapters WHERE id=?", (adapter_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="adapter not found")
    conn.execute(
        "INSERT INTO releases (adapter_id,version,gfa_compatibility,gcl_compatibility,capabilities,checksum,artifact_url,created_at) VALUES (?,?,?,?,?,?,?,?)",
        (adapter_id, req.version, req.gfa_compatibility, req.gcl_compatibility, json.dumps(req.capabilities),
         req.checksum, req.artifact_url, now()))
    conn.commit()
    return {"adapter_id": adapter_id, "version": req.version, "status": "recorded"}


@app.get("/adapters/{adapter_id}/releases")
def list_releases(adapter_id: str):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM releases WHERE adapter_id=? ORDER BY id DESC", (adapter_id,)).fetchall()
    return {"adapter_id": adapter_id, "releases": [row_to_dict(r) for r in rows]}


@app.post("/verify/checksum")
def verify_checksum(payload: dict[str, Any]):
    content = payload.get("content", "")
    expected = payload.get("expected")
    actual = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return {"match": actual == expected, "actual": actual, "expected": expected}