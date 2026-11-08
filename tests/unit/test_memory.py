import json
from pathlib import Path

from gfa.core.config import ConfigManager
from gfa.memory.extractor import ExperienceExtractor
from gfa.memory.manager import MemoryManager
from gfa.memory.models import MemoryRecord


def test_memory_crud_and_retrieval(tmp_path):
    cfg = ConfigManager(tmp_path / "c.json")
    cfg.set("data_dir", str(tmp_path / "data"))
    cfg.save()
    cfg2 = ConfigManager(cfg.path)
    mm = MemoryManager(cfg2)
    m1 = MemoryRecord(game_id="g", category="semantic", content="The red key opens the blue door", confidence=0.8, verification_status="verified")
    m2 = MemoryRecord(game_id="g", category="procedural", content="Jump over the gap to avoid damage", confidence=0.7)
    mm.add(m1)
    mm.add(m2)
    assert mm.stats()["total"] == 2
    got = mm.get(m1.id)
    assert got is not None and got.access_count >= 1
    # retrieval
    res = mm.retrieve("key door", game_id="g", limit=5)
    assert any("key" in r.content for r in res)
    # update version
    mm.update(m1.id, content="The red key opens the blue door (verified)")
    assert mm.versions(m1.id)
    # delete
    assert mm.delete(m2.id) is True
    assert mm.get(m2.id) is None
    mm.close()


def test_dedup_and_compress(tmp_path):
    cfg = ConfigManager(tmp_path / "c.json")
    cfg.set("data_dir", str(tmp_path / "data"))
    cfg.save()
    cfg2 = ConfigManager(cfg.path)
    mm = MemoryManager(cfg2)
    mm.add(MemoryRecord(game_id="g", category="semantic", content="enemy weak to fire", confidence=0.5))
    mm.add(MemoryRecord(game_id="g", category="semantic", content="enemy weak to fire damage", confidence=0.6))
    removed = mm.deduplicate(game_id="g", threshold=0.6)
    assert removed >= 1
    mm.close()


def test_export_import(tmp_path):
    cfg = ConfigManager(tmp_path / "c.json")
    cfg.set("data_dir", str(tmp_path / "data"))
    cfg.save()
    cfg2 = ConfigManager(cfg.path)
    mm = MemoryManager(cfg2)
    mm.add(MemoryRecord(game_id="g", category="episodic", content="fell into pit"))
    out = tmp_path / "mem.json"
    n = mm.export_json(out, game_id="g")
    assert n == 1
    # new db
    cfg3 = ConfigManager(tmp_path / "c2.json")
    cfg3.set("data_dir", str(tmp_path / "data2"))
    cfg3.save()
    cfg4 = ConfigManager(cfg3.path)
    mm2 = MemoryManager(cfg4)
    imported = mm2.import_json(out)
    assert imported == 1
    assert mm2.stats()["total"] == 1
    mm.close()
    mm2.close()


def test_memory_persists_across_restart_and_model_switch(tmp_path):
    cfg = ConfigManager(tmp_path / "c.json")
    cfg.set("data_dir", str(tmp_path / "data"))
    cfg.save()
    # Session 1 with "model A": store knowledge
    mm1 = MemoryManager(ConfigManager(cfg.path))
    mm1.add(MemoryRecord(game_id="g", category="semantic", content="The boss is weak to ice", confidence=0.9, verification_status="verified",
                         model_provenance="model-A"))
    mm1.close()
    # Restart + different model: retrieve
    mm2 = MemoryManager(ConfigManager(cfg.path))
    res = mm2.retrieve("boss weakness", game_id="g", limit=5)
    assert any("ice" in r.content for r in res)
    # model provenance preserved from previous
    assert any(r.model_provenance == "model-A" for r in res)
    mm2.close()


def test_extractor():
    ex = ExperienceExtractor(game_id="g", session_id="s")
    mems = ex.extract({"action": "move", "result": {"ok": True}, "success": True, "objective": "explore",
                       "new_objects": ["sword"], "location": "cave", "fact": "door is locked"})
    cats = [m.category for m in mems]
    assert "procedural" in cats
    assert "semantic" in cats
    assert "spatial" in cats
    assert len(mems) >= 4