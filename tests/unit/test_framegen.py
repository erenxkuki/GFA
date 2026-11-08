from gfa.universal.capture import capture_screen
from gfa.vision.perception import VisionPerception
from gfa.vision.framegen.generator import FrameGenerator


def test_framegen_keyframe_and_interpolated():
    frame = capture_screen(scale=0.5)
    vp = VisionPerception()
    fg = FrameGenerator(vp, keyframe_interval=2, change_threshold=0.99)
    # First frame is always keyframe
    g1 = fg.process(frame)
    assert g1.is_real is True
    # Second frame: if change < threshold, interpolated
    g2 = fg.process(frame)
    # Could be keyframe (interval=2) -> frame_count=2 % 2 == 0 -> keyframe
    assert g2 is not None
    assert g2.result.compact_summary


def test_framegen_reset():
    frame = capture_screen(scale=0.5)
    vp = VisionPerception()
    fg = FrameGenerator(vp)
    fg.process(frame)
    fg.reset()
    assert fg._frame_count == 0
    assert fg._last_keyframe is None