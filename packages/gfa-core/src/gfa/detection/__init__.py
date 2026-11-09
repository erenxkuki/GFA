"""Automatic game detection for GFA."""

from gfa.detection.detector import DetectedGame, GameDetector
from gfa.detection.profiles import GameProfile, GameProfileRegistry, default_profiles
from gfa.detection.windows import ForegroundWindow, get_foreground_window

__all__ = [
    "DetectedGame",
    "ForegroundWindow",
    "GameDetector",
    "GameProfile",
    "GameProfileRegistry",
    "default_profiles",
    "get_foreground_window",
]
