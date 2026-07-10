"""S7 tagging + the frozen cloud-route guard (INV-PII-3; docs/24 §3–4).

``tag`` marks PII-bearing context; ``cloud_route_allowed`` / ``require_cloud_allowed`` is the
one predicate every cloud adapter consults before sending — enforcement lives in S8, the
source of truth lives here (IF-3 seam).
"""

from __future__ import annotations

from dataclasses import replace

from charterhouse.security.scan import Scanner
from charterhouse.security.types import Context, PIIRouteBlocked


def tag(ctx: Context, scanner: Scanner) -> Context:
    """Return a copy with ``contains_pii=True`` iff the scan hits on ``ctx.text`` or any
    source ends ``.private.md``. Never clears an already-True flag. Pure."""
    if ctx.contains_pii:
        return ctx
    dirty = bool(scanner.scan(ctx.text)) or any(
        source.endswith(".private.md") for source in ctx.sources
    )
    return replace(ctx, contains_pii=True) if dirty else ctx


def cloud_route_allowed(ctx: Context) -> bool:
    """False iff ``ctx.contains_pii`` — the frozen guard (INV-PII-3). Pure."""
    return not ctx.contains_pii


def require_cloud_allowed(ctx: Context) -> None:
    """Raise ``PIIRouteBlocked`` iff the guard refuses — what a cloud adapter calls."""
    if not cloud_route_allowed(ctx):
        raise PIIRouteBlocked(
            "context is tagged contains_pii — cloud routes are excluded (INV-PII-3)"
        )
