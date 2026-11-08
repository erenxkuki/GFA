
from gfa.core.config import ConfigManager


def test_config_defaults_and_roundtrip(tmp_path):
    p = tmp_path / "config.json"
    cfg = ConfigManager(p)
    assert cfg.get("version") == 1
    cfg.set("foo.bar", 42)
    cfg.save()
    cfg2 = ConfigManager(p)
    assert cfg2.get("foo.bar") == 42


def test_config_missing_file_creates_default(tmp_path):
    p = tmp_path / "nope.json"
    cfg = ConfigManager(p)
    assert not p.exists()  # load doesn't write
    cfg.ensure_dirs()
    assert cfg.data_dir.exists()