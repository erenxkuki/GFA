from gfa.core.runtime import Runtime, RuntimeState


def test_runtime_lifecycle():
    import pathlib
    import tempfile

    from gfa.core.config import ConfigManager
    cfg = ConfigManager(pathlib.Path(tempfile.mkdtemp()) / "c.json")
    rt = Runtime(cfg)
    assert rt.state == RuntimeState.INITIALIZING
    rt.start()
    assert rt.state == RuntimeState.READY
    rt.mark_running()
    assert rt.state == RuntimeState.RUNNING
    h = rt.health()
    assert h.ok is True
    rt.pause()
    assert rt.state == RuntimeState.PAUSED
    rt.resume()
    assert rt.state == RuntimeState.RUNNING
    rt.stop()
    assert rt.state == RuntimeState.STOPPED


def test_session_manager(tmp_path):
    from gfa.core.config import ConfigManager
    from gfa.sessions.manager import SessionManager, SessionStatus
    cfg = ConfigManager(tmp_path / "c.json")
    cfg.ensure_dirs()
    # override data_dir to tmp
    cfg.set("data_dir", str(tmp_path / "data"))
    cfg.save()
    cfg2 = ConfigManager(cfg.path)
    cfg2.ensure_dirs()
    sm = SessionManager(cfg2)
    rec = sm.create(game="TestGame", model_provider="ollama", model_id="llama3")
    assert rec.session_id.startswith("ses_")
    assert sm.get(rec.session_id).game == "TestGame"
    sm.record_action(rec.session_id, {"type": "move"}, {"ok": True})
    sm.update_status(rec.session_id, SessionStatus.COMPLETED)
    rec2 = sm.get(rec.session_id)
    assert rec2.status == "completed"
    assert rec2.action_count == 1
    assert len(sm.list()) == 1