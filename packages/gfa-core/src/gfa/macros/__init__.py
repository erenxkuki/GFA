"""Macro recording & playback: capture input sequences, replay them later."""

from gfa.macros.library import MacroLibrary, MacroLibraryError
from gfa.macros.models import Macro, MacroStep
from gfa.macros.player import MacroPlayer, PlaybackResult
from gfa.macros.recorder import MacroRecorder

__all__ = [
    "Macro",
    "MacroLibrary",
    "MacroLibraryError",
    "MacroPlayer",
    "MacroRecorder",
    "MacroStep",
    "PlaybackResult",
]
