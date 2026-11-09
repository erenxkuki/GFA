import asyncio

from gfa.agent.agent import GameplayAgent
from gfa.agent.reasoning import ReasoningCoordinator
from gfa.detection import GameDetector, GameProfile, GameProfileRegistry
from gfa.detection.windows import ForegroundWindow
from gfa.universal.baseline import BaselineConfig, UniversalBaseline
from gfa.universal.capture import CapturedFrame


class FakeBaseline:
    def __init__(self, frame):
        self.frame = frame
        self.applied_game = None

    def observe(self):
        return self.frame

    def capabilities(self):
        from gfa.gcl.capabilities import CapabilitySet

        return CapabilitySet.core_capabilities()

    def register_gcl_handlers(self, executor):
        async def wait_handler(cmd):
            return {"duration_ms": 1}

        executor.register_handler("wait", wait_handler)

    def emergency_stop(self):
        pass

    def apply_detected_game(self):
        self.applied_game = "minecraft"
        return {"game_id": "minecraft", "confidence": 0.9}


def _window(title: str, proc: str, hwnd: int = 1, pid: int = 1) -> ForegroundWindow:
    return ForegroundWindow(hwnd=hwnd, title=title, pid=pid, process_name=proc)


def test_registry_crud_and_persistence(tmp_path):
    reg = GameProfileRegistry(tmp_path)
    # seeded defaults exist
    assert reg.get("minecraft") is not None
    assert reg.get("zzz") is not None

    reg.register(GameProfile(game_id="mygame", name="My Game",
                             title_keywords=["mygame"], process_keywords=["mygame.exe"],
                             keybind_preset="fps-wasd"))
    assert reg.get("mygame") is not None

    # persist: fresh registry on the same tmp dir sees it
    reg2 = GameProfileRegistry(tmp_path)
    assert reg2.get("mygame") is not None
    assert len(reg2.list()) == len(reg.list())

    assert reg2.remove("mygame") is True
    assert reg2.get("mygame") is None
    assert reg2.remove("mygame") is False


def test_profile_scoring():
    prof = GameProfile(game_id="minecraft", title_keywords=["minecraft"],
                       process_keywords=["javaw.exe"])
    assert prof.score(_window("Minecraft 1.20", "javaw.exe")) > 0.5
    assert prof.score(_window("Unrelated", "other.exe")) == 0.0
    assert prof.score(None) == 0.0
    # exact title match bonus
    assert prof.score(_window("minecraft", "x.exe")) >= 0.2


def test_registry_match_best(tmp_path):
    reg = GameProfileRegistry(tmp_path)
    matches = reg.match(_window("Minecraft 1.20", "javaw.exe"))
    assert len(matches) >= 1
    profile, score = reg.best(_window("Minecraft 1.20", "javaw.exe"))
    assert profile.game_id == "minecraft"
    assert score >= 0.5

    assert reg.best(_window("Calculator", "calc.exe")) is None
    assert reg.match(_window("Calculator", "calc.exe")) == []


def test_detector_with_fake_provider(tmp_path):
    window = _window("Zenless Zone Zero - New Eridu", "ZenlessZoneZero.exe")
    reg = GameProfileRegistry(tmp_path)
    detector = GameDetector(registry=reg, window_provider=lambda: window)
    detected = detector.detect()
    assert detected.window.title == window.title
    assert detected.profile is not None
    assert detected.profile.game_id == "zzz"
    assert detected.confidence >= 0.5
    assert detected.candidates
    data = detected.to_dict()
    assert data["profile"]["game_id"] == "zzz"
    assert "Detected game: Zenless" in detected.to_text()


def test_detector_unknown_and_none_window(tmp_path):
    reg = GameProfileRegistry(tmp_path)
    detector = GameDetector(registry=reg, window_provider=lambda: None)
    detected = detector.detect()
    assert detected.window is None
    assert detected.profile is None
    assert detected.confidence == 0.0

    detector2 = GameDetector(registry=reg, window_provider=lambda: _window("Foo Bar", "foo.exe"))
    detected2 = detector2.detect()
    assert detected2.profile is None


def test_baseline_apply_detected_game(tmp_path, monkeypatch):
    bl = UniversalBaseline(BaselineConfig(capture_scale=1.0, data_dir=tmp_path))

    def fake_detect(self):
        from gfa.detection.detector import DetectedGame

        return DetectedGame(window=_window("Minecraft", "javaw.exe"),
                            profile=GameProfile(game_id="minecraft", keybind_preset="fps-wasd"),
                            confidence=0.9, candidates=[("minecraft", 0.9)])

    monkeypatch.setattr("gfa.detection.detector.GameDetector.detect", fake_detect)
    result = bl.apply_detected_game()
    assert result is not None
    assert result["game_id"] == "minecraft"
    assert result["keybind_applied"] is True
    # keybind profile actually assigned
    assert bl.keybinds.move_forward_key in ("w", "W") or bl.keybinds.move_forward_key == "w"


def test_baseline_apply_detected_game_unknown(tmp_path, monkeypatch):
    bl = UniversalBaseline(BaselineConfig(capture_scale=1.0, data_dir=tmp_path))

    def fake_detect(self):
        from gfa.detection.detector import DetectedGame

        return DetectedGame(window=_window("Foo", "foo.exe"), profile=None,
                            confidence=0.0, candidates=[])

    monkeypatch.setattr("gfa.detection.detector.GameDetector.detect", fake_detect)
    result = bl.apply_detected_game()
    assert result is not None
    assert result["game_id"] is None
    assert result["keybind_applied"] is False


def test_agent_auto_detects_game():
    async def run():
        baseline = FakeBaseline(CapturedFrame(width=100, height=100, png_bytes=b"x"))
        reasoning = ReasoningCoordinator(fallback_policy=lambda ws: [{"type": "wait", "duration_ms": 1}])
        captured = {}

        def fb(ws):
            captured["ws"] = ws
            return [{"type": "wait", "duration_ms": 1}]

        reasoning.fallback_policy = fb
        agent = GameplayAgent(baseline=baseline, reasoning=reasoning,
                              auto_detect_game=True, max_steps=1, step_delay=0.0)
        result = await agent.run("win", game=None)
        assert result.steps == 1
        assert baseline.applied_game == "minecraft"
        # detected game feeds the world state's game field
        assert captured["ws"].game == "minecraft"

    asyncio.run(run())
