import time

from gfa.latency.optimizer import LatencyOptimizer, LatencyTracker, FrameSkipper
from gfa.latency.speculative import SpeculativeExecutor, InputCoalescer


def test_latency_tracker():
    lt = LatencyTracker()
    from gfa.latency.optimizer import LatencyMetrics
    lt.record(LatencyMetrics(total_ms=50, capture_ms=5, perception_ms=10, reasoning_ms=30, execution_ms=5))
    lt.record(LatencyMetrics(total_ms=60, capture_ms=6, perception_ms=12, reasoning_ms=35, execution_ms=7))
    assert lt.avg_total() == 55.0
    assert lt.max_total() == 60.0
    assert lt.avg_capture() == 5.5
    r = lt.report()
    assert "avg_total_ms" in r


def test_frame_skipper():
    fs = FrameSkipper(target_fps=30, min_skip=1, max_skip=3)
    # First frame should process
    assert fs.should_process() is True


def test_latency_optimizer_ocr():
    opt = LatencyOptimizer(ocr_every_n=3)
    assert opt.should_run_ocr() is True  # frame 1
    assert opt.should_run_ocr() is False  # frame 2
    assert opt.should_run_ocr() is False  # frame 3
    assert opt.should_run_ocr() is True  # frame 4


def test_latency_optimizer_change_detection():
    from gfa.universal.capture import capture_screen
    frame = capture_screen(scale=0.25)
    opt = LatencyOptimizer()
    change = opt.update_change(frame)
    assert 0.0 <= change <= 1.0
    # Same frame again -> low change
    change2 = opt.update_change(frame)
    assert change2 == 0.0


def test_speculative_executor():
    se = SpeculativeExecutor(confidence_threshold=0.5)
    assert se.should_speculate(0.8) is True
    assert se.should_speculate(0.3) is False
    se.learn("state1", [{"type": "move", "direction": "forward"}])
    pred = se.predict("state1")
    assert pred is not None
    assert pred[0]["type"] == "move"
    se.record(__import__("gfa.latency.speculative", fromlist=["SpeculativeAction"]).SpeculativeAction(
        commands=[{"type": "wait"}], correct=True))
    assert se.accuracy == 1.0
    assert se.stats()["cached_patterns"] == 1


def test_input_coalescer():
    co = InputCoalescer(max_batch=3, flush_interval_ms=100)
    co._last_flush = time.time()  # simulate recent flush
    co.add("a")
    co.add("b")
    assert co.pending_count == 2
    assert co.should_flush() is False  # not enough time
    batch = co.flush()
    assert len(batch) == 2
    assert co.pending_count == 0