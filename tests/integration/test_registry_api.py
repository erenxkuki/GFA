import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps" / "registry-api"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages" / "gfa-core" / "src"))

from fastapi.testclient import TestClient

import main as registry_main
from main import app


def test_registry_submit_search_retrieve(tmp_path, monkeypatch):
    db = tmp_path / "reg.db"
    monkeypatch.setattr(registry_main, "DB_PATH", db)
    # also patch database connect default? main uses DB_PATH global in get_conn via main.DB_PATH? get_conn uses DB_PATH name in main module
    client = TestClient(app)

    # health
    r = client.get("/health")
    assert r.status_code == 200

    # submit via local manifest
    repo = Path(__file__).resolve().parents[2] / "official-adapters" / "gfa-reference-game"
    r = client.post("/adapters/submit", json={"repository": str(repo), "owner_token": "tok"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "approved"
    aid = data["adapter_id"]

    # list
    r = client.get("/adapters", params={"q": "reference"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    # get
    r = client.get(f"/adapters/{aid}")
    assert r.status_code == 200
    assert r.json()["id"] == aid

    # add release
    r = client.post(f"/adapters/{aid}/releases", json={"version": "1.0.0", "capabilities": ["game.move"]})
    assert r.status_code == 200
    r = client.get(f"/adapters/{aid}/releases")
    assert r.json()["releases"]

    # checksum
    r = client.post("/verify/checksum", json={"content": "abc", "expected": __import__("hashlib").sha256(b"abc").hexdigest()})
    assert r.json()["match"] is True

    # pagination
    r = client.get("/adapters", params={"limit": 1, "offset": 0})
    assert r.status_code == 200
    assert len(r.json()["items"]) <= 1