"""``FakeEmbedder`` — deterministic fixed-dimension vectors (docs/55 §2).

Stands in for the local embedder (S9/Embeddings.embed). Same text → same vector, no model
or network. Vectors are unit-norm so cosine-similarity tests are stable.
"""

from __future__ import annotations

import hashlib
import math


class FakeEmbedder:
    """Deterministic embedder. ``embed(text)`` returns a length-``dim`` unit vector derived
    from a hash of the text — reproducible across runs and machines."""

    def __init__(self, dim: int = 64) -> None:
        if dim <= 0:
            raise ValueError("dim must be positive")
        self._dim = dim

    def embed(self, text: str) -> tuple[float, ...]:
        raw = hashlib.sha256(text.encode("utf-8")).digest()
        # Stretch the digest deterministically to `dim` floats in [-1, 1).
        vals = []
        i = 0
        while len(vals) < self._dim:
            h = hashlib.sha256(raw + i.to_bytes(4, "big")).digest()
            for b in h:
                if len(vals) >= self._dim:
                    break
                vals.append((b / 127.5) - 1.0)
            i += 1
        norm = math.sqrt(sum(v * v for v in vals)) or 1.0
        return tuple(v / norm for v in vals)

    @property
    def dim(self) -> int:
        return self._dim
