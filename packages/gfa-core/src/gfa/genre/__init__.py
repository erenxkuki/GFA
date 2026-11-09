"""Genre-specific HUD perception models."""

from gfa.genre.detectors import DetectedElement, GenreDetector
from gfa.genre.profiles import (
    GENRE_PROFILES,
    ElementConfig,
    GenreProfile,
    get_genre,
    list_genres,
    select_genre_for_keywords,
)

__all__ = [
    "GENRE_PROFILES",
    "DetectedElement",
    "ElementConfig",
    "GenreDetector",
    "GenreProfile",
    "get_genre",
    "list_genres",
    "select_genre_for_keywords",
]
