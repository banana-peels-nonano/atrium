"""S9 embeddings — the ``Embeddings`` protocol + the LOCAL-ONLY ``OllamaEmbedder``
(memory/API.md, docs/33 embedding contract).

Locality by construction (INV-MEM-4 second clause): the sole production implementation
posts to the loopback Ollama endpoint from ``EnvContext``; **no cloud embedder class
exists in this subsystem**. The HTTP transport is injected so tests never open a socket
(INV-TEST-SAFE); A11's ``FakeEmbedder`` implements this protocol for everything else.

Determinism (docs/61 §INV-DET): the embedder is a local encoder, not a generator — no
LLM call, no env read (host/model arrive from A1's preflight ``EnvContext`` at wiring).
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from charterhouse.memory.types import EmbedFailed

__all__ = ["Embeddings", "OllamaEmbedder", "EmbedFailed"]


@runtime_checkable
class Embeddings(Protocol):
    """The frozen embed surface (docs/40 §6): text → fixed-dimension vector, locally."""

    def embed(self, text: str) -> tuple[float, ...]: ...

    @property
    def dim(self) -> int: ...


# transport(url, json_body) -> parsed JSON dict. Injected; the default below is the real
# loopback HTTP transport, wired only in production (same seam pattern as S8 key_lookup).
Transport = Callable[[str, dict], dict]


def _default_transport(url: str, body: dict) -> dict:  # pragma: no cover — real HTTP
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:  # noqa: S310 — loopback Ollama only
        return json.loads(resp.read().decode("utf-8"))


class OllamaEmbedder:
    """``Embeddings`` over a local Ollama ``/api/embeddings`` endpoint. ``model`` is the
    pinned ``CHARTERHOUSE_EMBED_MODEL`` id (via ``EnvContext.embed_model``, never env)."""

    def __init__(self, host: str, model: str, dim: int,
                 transport: Transport | None = None) -> None:
        self._url = host.rstrip("/") + "/api/embeddings"
        self._model = model
        self._dim = dim
        self._transport = transport if transport is not None else _default_transport

    def embed(self, text: str) -> tuple[float, ...]:
        """One local embed call. Transport/shape failure → ``EmbedFailed`` (fail closed,
        no retry loop, no cloud fallback — none exists)."""
        try:
            data = self._transport(self._url, {"model": self._model, "prompt": text})
        except Exception as exc:
            raise EmbedFailed(
                f"local embedding endpoint failed for model {self._model!r}: "
                f"{type(exc).__name__}") from exc
        vec = data.get("embedding") if isinstance(data, dict) else None
        if not isinstance(vec, list) or len(vec) != self._dim:
            got = len(vec) if isinstance(vec, list) else "none"
            raise EmbedFailed(
                f"embedding shape mismatch for model {self._model!r}: expected "
                f"dim {self._dim}, got {got}")
        return tuple(float(v) for v in vec)

    @property
    def dim(self) -> int:
        return self._dim
