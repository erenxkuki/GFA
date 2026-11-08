from gfa.universal.capture import capture_screen
from gfa.vision.perception import VisionPerception
from gfa.vision.optimizer import TokenOptimizer


def test_vision_perception_compact_summary():
    frame = capture_screen(scale=0.25)
    vp = VisionPerception(color_map={"red": (200, 0, 0)}, tolerance=80)
    res = vp.analyze(frame)
    assert res.compact_summary
    assert res.frame_size == (frame.width, frame.height)
    assert isinstance(res.objects, list)


def test_token_optimizer_estimate():
    est = TokenOptimizer.estimate_tokens("hello world", has_image=False)
    assert est > 0
    est2 = TokenOptimizer.estimate_tokens("hello world", has_image=True)
    assert est2 > est


def test_token_optimizer_build_payload_compact():
    frame = capture_screen(scale=0.25)
    opt = TokenOptimizer(mode="compact")
    payload = opt.build_payload(frame, "test summary")
    assert payload["text"] == "test summary"
    assert "image_base64" not in payload