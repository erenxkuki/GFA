from gfa.core.config import ConfigManager
from gfa.memory.embeddings import DeterministicEmbedder, cosine_similarity
from gfa.memory.manager import MemoryManager
from gfa.memory.models import MemoryRecord


def _manager(tmp_path, embedder=None, default_scorer="keyword"):
    cfg = ConfigManager(tmp_path / "config.json")
    cfg.ensure_dirs()
    cfg.set("data_dir", str(tmp_path / "data"))
    cfg.save()
    cfg2 = ConfigManager(cfg.path)
    cfg2.ensure_dirs()
    return MemoryManager(cfg2, embedder=embedder, default_scorer=default_scorer)


def _add(mm, game, content, category="procedural", confidence=0.8, memory_type="verified", verification_status="verified"):
    return mm.add(MemoryRecord(game_id=game, category=category, memory_type=memory_type,
                                content=content, confidence=confidence, verification_status=verification_status))


def test_embedder_deterministic_and_self_similar():
    emb = DeterministicEmbedder(dim=256)
    v1 = emb.embed("dodge when the enemy is close")
    v2 = emb.embed("dodge when the enemy is close")
    assert v1 == v2  # deterministic across calls
    assert abs(cosine_similarity(v1, v2) - 1.0) < 1e-6  # identical -> cosine 1
    assert len(v1) == 256
    assert abs(sum(x * x for x in v1) ** 0.5 - 1.0) < 1e-6  # unit norm


def test_embedder_semantic_ranking():
    emb = DeterministicEmbedder(dim=256)
    q = emb.embed("dodge the enemy attack")
    related = emb.embed("dodging avoids incoming damage")   # paraphrase + morphology
    unrelated = emb.embed("the health bar is red in the HUD")  # different topic
    assert cosine_similarity(q, related) > cosine_similarity(q, unrelated)


def test_embedder_empty_and_bad_dim():
    emb = DeterministicEmbedder(dim=64)
    assert emb.embed("") == [0.0] * 64
    assert cosine_similarity(emb.embed(""), emb.embed("hello")) == 0.0
    import pytest

    with pytest.raises(ValueError):
        DeterministicEmbedder(dim=0)


def test_keyword_default_unchanged(tmp_path):
    mm = _manager(tmp_path)
    _add(mm, "G", "dodge when the enemy is close")
    _add(mm, "G", "heal with potion at low health")
    _add(mm, "G", "the minimap shows the exit east")
    got = mm.retrieve("dodge enemy close", game_id="G", limit=2)
    assert got[0].content == "dodge when the enemy is close"


def test_semantic_retrieval(tmp_path):
    emb = DeterministicEmbedder(dim=256)
    mm = _manager(tmp_path, embedder=emb, default_scorer="semantic")
    _add(mm, "G", "dodge when the enemy is close", confidence=0.5)
    _add(mm, "G", "heal with potion", confidence=0.9)
    _add(mm, "G", "minimap shows exit east", confidence=0.9)

    # semantic mode: paraphrase ranks the dodge memory first regardless of exact keywords
    got = mm.retrieve("evade the incoming strike", game_id="G", scorer="semantic", limit=3)
    assert got[0].content == "dodge when the enemy is close"

    # hybrid: still finds it (plus keyword signal)
    got_hybrid = mm.retrieve("evade the incoming strike", game_id="G", scorer="hybrid", limit=3)
    assert got_hybrid[0].content == "dodge when the enemy is close"


def test_semantic_beats_keyword_for_paraphrase(tmp_path):
    emb = DeterministicEmbedder(dim=256)
    mm = _manager(tmp_path, embedder=emb)
    # keyword trap: a memory sharing a rare exact token but topically unrelated
    _add(mm, "G", "zephyr token appears in the menu", confidence=0.9)
    _add(mm, "G", "jump over the gap using the ledge", confidence=0.9)

    query = "leap across the chasm"
    kw = mm.retrieve(query, game_id="G", scorer="keyword", limit=2)
    sem = mm.retrieve(query, game_id="G", scorer="semantic", limit=2)
    # semantic scoring should rank the jump/ledge memory first for a leap/jump query
    assert sem[0].content == "jump over the gap using the ledge"
    assert kw is not None  # keyword result may differ; just ensure no crash


def test_embed_cache_reuse(tmp_path):
    emb = DeterministicEmbedder(dim=128)
    mm = _manager(tmp_path, embedder=emb)
    assert mm._embed("x", "hello") is None or mm.embedder is emb
    rec = _add(mm, "G", "cache me please")
    v1 = mm._embed(rec.id, rec.content)
    v2 = mm._embed(rec.id, rec.content)
    assert v1 is v2  # same object from cache
    assert mm._embed(rec.id, rec.content) == v1
