
from gfa.core.config import ConfigManager
from gfa.models.base import ModelConfig
from gfa.models.manager import ModelManager


def test_model_manager_crud(tmp_path):
    cfg = ConfigManager(tmp_path / "c.json")
    cfg.set("data_dir", str(tmp_path / "data"))
    cfg.save()
    cfg2 = ConfigManager(cfg.path)
    mm = ModelManager(cfg2)
    m = ModelConfig(id="m1", provider="ollama", endpoint="http://localhost:11434", model="llama3")
    mm.add(m, api_key="secret123")
    assert mm.resolve_secret("m1") == "secret123"
    # secret not in config
    raw = cfg2.get("models")
    assert all("api_key" not in x or x.get("api_key") is None for x in raw)
    assert mm.get_active() is None
    mm.set_active("m1")
    assert mm.get_active() == "m1"
    assert mm.remove("m1") is True
    assert mm.resolve_secret("m1") is None


def test_credential_store_roundtrip(tmp_path):
    from gfa.models.manager import CredentialStore
    cs = CredentialStore(tmp_path / "data")
    cs.set("k", "v")
    cs2 = CredentialStore(tmp_path / "data")
    assert cs2.get("k") == "v"
    assert cs2.delete("k") is True
    assert cs2.get("k") is None