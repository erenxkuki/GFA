"""Game genre profiles for real-time action tuning."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GenreProfile:
    name: str
    target_fps: int = 30  # perception rate
    step_delay: float = 0.033
    reflex_priority: bool = True
    aim_assist: bool = False
    motion_prediction: bool = True
    input_smoothing: bool = False
    steering_deadzone: float = 0.0
    max_lookahead_ms: int = 200
    action_buffer_size: int = 8
    ocr_every_n: int = 5
    capture_scale: float = 0.4
    mouse_sensitivity: float = 1.0
    key_repeat_rate: float = 0.016  # ~60Hz


STORY = GenreProfile(name="story", target_fps=10, step_delay=0.1, ocr_every_n=1,
                     capture_scale=0.5, motion_prediction=False, input_smoothing=False)

SHOOTER = GenreProfile(name="shooter", target_fps=30, step_delay=0.033, aim_assist=True,
                       motion_prediction=True, input_smoothing=False, ocr_every_n=5,
                       capture_scale=0.4, mouse_sensitivity=1.5, key_repeat_rate=0.016)

RACING = GenreProfile(name="racing", target_fps=30, step_delay=0.033, aim_assist=False,
                      motion_prediction=True, input_smoothing=True, steering_deadzone=0.05,
                      ocr_every_n=8, capture_scale=0.35, key_repeat_rate=0.016)

FIGHTING = GenreProfile(name="fighting", target_fps=60, step_delay=0.016, aim_assist=False,
                        motion_prediction=False, input_smoothing=False, ocr_every_n=10,
                        capture_scale=0.4, key_repeat_rate=0.016)

PLATFORMER = GenreProfile(name="platformer", target_fps=30, step_delay=0.033, aim_assist=False,
                          motion_prediction=True, input_smoothing=False, ocr_every_n=5,
                          capture_scale=0.4, key_repeat_rate=0.016)

GENRE_PROFILES = {
    "story": STORY,
    "shooter": SHOOTER,
    "racing": RACING,
    "fighting": FIGHTING,
    "platformer": PLATFORMER,
}