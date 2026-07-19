"""Frozen IF-2 (Config half) shared types — Route, Model, Provider, Budgets (docs/40 §1;
BUILD_TRACKER 2026-07-04 interface-freeze row).

Declarations only, transcribed verbatim from the frozen shapes: loading, validation
(INV-CFG: every route model exists in models), profiles, and the ``Config`` surface are
S3's (A2) to implement. Consumers that must not wait on S3 (Governance's founder-wide
send budget, INV-GOV-5; Router's role resolution) depend on these shapes and stub the
``Config`` accessor per docs/43 §2.

Determinism (docs/61 §INV-DET): stdlib only; no ``router`` / ``memory`` / ``capabilities``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    """A role→model routing rule (docs/40 §1): ``{primary, fallback[], min_ctx?,
    needs_tools?, needs_web?}``. Roles, never model ids, cross the LLMClient seam."""

    primary: str
    fallback: tuple[str, ...] = ()
    min_ctx: int | None = None
    needs_tools: bool | None = None
    needs_web: bool | None = None


@dataclass(frozen=True)
class Model:
    """A model catalog entry (docs/40 §1): ``{provider, ctx, price_in, price_out, tier,
    good_at[]}``. Prices are USD per million tokens (docs/22).

    ``family`` is the **additive** docs/43 §7 field (capabilities RISKS R3, founder
    follow-up at the A8 gate): the model family the INV-WF-2 cross-family critic check
    compares. The loader always fills it — an explicit ``family:`` key in models.yaml
    wins; otherwise ``default_family(id)`` derives it. Empty only on hand-built stubs.
    """

    provider: str
    ctx: int
    price_in: float
    price_out: float
    tier: str
    good_at: tuple[str, ...] = ()
    family: str = ""


def default_family(model_id: str) -> str:
    """The canonical family derivation — the model id's leading alphabetic token,
    lowercased (``claude-sonnet``→``claude``, ``llama3.1-8b-local``→``llama``). ONE home
    (this module): S3's loader uses it to default ``Model.family``; nothing else parses
    model ids for families (the critic's interim heuristic is retired — A8 RISKS R3)."""
    letters = []
    for ch in model_id:
        if ch.isalpha():
            letters.append(ch.lower())
        else:
            break
    return "".join(letters) if letters else model_id.lower()


@dataclass(frozen=True)
class MemoryConfig:
    """The S9 retrieval/consolidation tuning block (docs/33 "weights in config,
    tunable"; memory RISKS R9) — the **additive** ``Config.memory`` accessor's shape,
    mirroring ``RetrievalWeights`` field-for-field with the same frozen defaults.
    Optional ``memory:`` block in routes.yaml; absent keys keep these defaults."""

    w_semantic: float = 0.5
    w_tag: float = 0.2
    w_recency: float = 0.15
    w_confidence: float = 0.15
    w_segment: float = 0.1
    half_life_active: float = 30.0
    dup_threshold: float = 0.995
    retire_below: float = 0.2
    promote_min_ventures: int = 3
    max_k: int = 16


@dataclass(frozen=True)
class Provider:
    """A provider endpoint (docs/40 §1): ``{base_url, key_env, kind}``. ``key_env`` names
    the environment variable holding the key — secrets never live in config files
    (docs/24 secrets handling); the Router reads keys from env at call time."""

    base_url: str
    key_env: str
    kind: str


@dataclass(frozen=True)
class Budgets:
    """The factory budget envelope (docs/40 §1): ``{monthly_usd, on_exceeded, send_daily}``.

    ``send_daily`` is the founder-wide daily send budget (R-SEND-BUDGET, INV-GOV-5):
    a single cap across ALL ventures, Conductor-allocated by priority — never a
    per-venture allowance. ``on_exceeded`` names the degrade policy applied when the
    monthly budget is exhausted (docs/25).
    """

    monthly_usd: float
    on_exceeded: str
    send_daily: int
