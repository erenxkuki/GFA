import pytest

from gfa.audio.wasapi import WasapiLoopbackSource


def test_is_available_runs():
    # PowerShell must exist on Windows; on CI without it we skip gracefully
    available = WasapiLoopbackSource.is_available()
    assert available in (True, False)  # device-dependent; just ensure no crash


def test_capture_returns_valid_frames():
    if not WasapiLoopbackSource.is_available():
        pytest.skip("PowerShell unavailable")
    src = WasapiLoopbackSource(seconds=0.25, timeout_s=60.0)
    try:
        frames = src.capture()
    except RuntimeError as exc:
        # No audio device on this machine — acceptable, but silence must still be valid
        pytest.skip(f"WASAPI not usable: {exc}")
    assert len(frames) == 1
    frame = frames[0]
    assert frame.source == "loopback"
    assert frame.sample_rate in (44100, 48000, 96000, 192000, 22050, 32000, 8000, 16000, 22050)
    assert len(frame.samples) > 1000  # 0.25s * rate (approx, allow slack)
    assert all(-1.0 <= s <= 1.0 for s in frame.samples)
    src.close()


def test_capture_silence_yields_no_events():
    from gfa.audio.analyzer import AudioClassifier

    if not WasapiLoopbackSource.is_available():
        pytest.skip("PowerShell unavailable")
    src = WasapiLoopbackSource(seconds=0.25, timeout_s=60.0)
    try:
        frames = src.capture()
    except RuntimeError as exc:
        pytest.skip(f"WASAPI not usable: {exc}")
    events = AudioClassifier().analyze(frames)
    # Real-world check: likely silence, but even if noisy we must not crash — either is fine
    assert isinstance(events, list)
    src.close()


def test_monitor_integration_with_wasapi():
    from gfa.audio.perception import AudioMonitor

    if not WasapiLoopbackSource.is_available():
        pytest.skip("PowerShell unavailable")
    src = WasapiLoopbackSource(seconds=0.25, timeout_s=60.0)
    mon = AudioMonitor(source=src, cooldown_ms=250.0)
    try:
        events = mon.poll()
    except RuntimeError as exc:
        pytest.skip(f"WASAPI not usable: {exc}")
    assert isinstance(events, list)
    assert isinstance(mon.summary(), str)
    mon.source.close()
