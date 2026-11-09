"""Semantic embeddings for memory retrieval.

Implements a dependency-free deterministic embedding: each token and each
character 3-gram is hash-projected into a fixed-dimensional vector. Same
tokens/grams map to the same coordinates, so retrieval becomes cosine
similarity over a semantic space rather than raw keyword overlap — matching
paraphrases and morphological variants ("dodge" ~ "dodging ~ "evade"-free
variants) far better than Jaccard token sets.

For richer semantics, pass a stronger embedder (e.g., a model-backed one)
via the :class:`Embedder` protocol — nothing else needs to change.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

from gfa.memory.models import tokenize


class Embedder(Protocol):
    """Anything that can embed text into a fixed-width float vector."""

    def embed(self, text: str) -> list[float]: ...


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity in [-1, 1]; 0.0 for zero/empty vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class DeterministicEmbedder:
    """Hash-based embedding: word tokens + character 3-grams.

    - Deterministic across processes (md5-based, not salted ``hash()``).
    - No dependencies — runs anywhere (model-independence by design).
    - Char 3-grams capture morphology ("dodge"/"dodging"/"jump"/"jumping").
    """

    def __init__(self, dim: int = 256):
        if dim <= 0:
            raise ValueError("dim must be positive")
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        if not text:
            return vec
        tokens = tokenize(text)
        for tok in tokens:
            self._accumulate(vec, tok)
            # character 3-grams with spaces as boundaries
            padded = f" {tok} "
            for i in range(len(padded) - 2):
                gram = padded[i:i + 3]
                self._accumulate(vec, gram)
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def _accumulate(self, vec: list[float], feature: str) -> None:
        h = hashlib.md5(feature.encode("utf-8")).digest()
        idx = int.from_bytes(h[0:4], "little") % self.dim
        sign = 1.0 if h[4] % 2 == 0 else -1.0
        vec[idx] += sign


def embedder_name(embedder: Embedder | None) -> str:
    return getattr(type(embedder), "__name__", "none") if embedder is not None else "none"
