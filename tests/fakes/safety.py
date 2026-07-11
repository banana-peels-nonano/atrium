"""INV-TEST-SAFE guard (docs/55 §6): no test performs a real spend/send/deploy/charge.

The boundary is explicit: any code path that would perform a real, irreversible external
action calls ``guard_real_action(name)``. In production that is wired to the real effector;
under the test harness it is always blocked (``RealActionBlocked``), so a test that reaches
a real action fails loudly instead of doing it. Tests assert only up to the authorization
boundary (token minting / event append), never the effect.
"""

from __future__ import annotations


class RealActionBlocked(Exception):
    """A real side-effecting action was attempted under the test harness (INV-TEST-SAFE)."""


def guard_real_action(name: str) -> None:
    """Block a real external action under test. Never returns — always raises."""
    raise RealActionBlocked(
        f"real action {name!r} is blocked under the test harness (INV-TEST-SAFE, docs/55 "
        "§6); tests assert up to the authorization boundary only")
