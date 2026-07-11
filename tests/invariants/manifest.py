"""The INV-* → test-name manifest + completeness logic (docs/55 §4; logging/API.md
``invariant_manifest``).

Every invariant maps to the named test(s) that prove it. The **INV-SM lifecycle family** is
authoritative and CI-enforced now that S5 is real (gate 2, the founder's ask). Other
families are declared in ``REQUIRED_INVARIANTS`` and will be mapped here as A11 hoists the
governance/security/ledger suites into the shared harness — until then ``unmapped`` reports
them truthfully, but gate 2 checks only the family it is asked to.

Pure data + pure functions (no pytest import): the CLI checker
(``scripts/invariant_check.py``) verifies each mapped node id is actually collectable.
"""

from __future__ import annotations

# INV id -> the pytest node ids (file::test) that prove it. Node ids are verified
# collectable by scripts/invariant_check.py; a typo fails the gate, not silently passes.
INVARIANT_MANIFEST: dict[str, tuple[str, ...]] = {
    # INV-SM lifecycle family (S5) — authoritative, gate-2 enforced.
    "INV-SM-1": (
        "tests/unit/test_lifecycle.py::test_table_matches_docs42_verbatim",
        "tests/unit/test_lifecycle.py::test_full_matrix_legal_vs_illegal",
        "tests/unit/test_lifecycle.py::test_illegal_reject_leaves_state_unchanged",
    ),
    "INV-SM-2": (
        "tests/unit/test_lifecycle.py::test_validating_wip_le_3",
        "tests/unit/test_lifecycle.py::test_shaping_wip_eq_1",
        "tests/unit/test_lifecycle.py::test_building_wip_le_1",
        "tests/unit/test_lifecycle.py::test_harvest_alumni_cap_le_3",
    ),
    "INV-SM-3": (
        "tests/unit/test_lifecycle.py::test_deadline_from_experiment_live_not_entry",
        "tests/unit/test_lifecycle.py::test_pause_freezes_active_time",
        "tests/unit/test_lifecycle.py::test_state_windows_in_active_days",
    ),
    "INV-SM-4": (
        "tests/unit/test_lifecycle.py::test_express_only_launched_to_earning",
    ),
    "INV-SM-5": (
        "tests/unit/test_lifecycle.py::test_pivot_kill_and_fork",
        "tests/unit/test_lifecycle.py::test_second_fork_in_lineage_refused",
        "tests/unit/test_lifecycle.py::test_omw_once_per_lineage",
    ),
    "INV-SM-6": (
        "tests/unit/test_lifecycle.py::test_ttl_stale_shovel_ready_blocked",
    ),
}

# The invariants each family MUST cover (docs/54). A member with no manifest entry is an
# unmapped MUST. Only the family gate 2 is asked to check must be fully mapped today.
REQUIRED_INVARIANTS: dict[str, tuple[str, ...]] = {
    "INV-SM": ("INV-SM-1", "INV-SM-2", "INV-SM-3", "INV-SM-4", "INV-SM-5", "INV-SM-6"),
    "INV-GOV": ("INV-GOV-1", "INV-GOV-2", "INV-GOV-3", "INV-GOV-4", "INV-GOV-5",
                "INV-GOV-6"),
    "INV-PII": ("INV-PII-1", "INV-PII-2", "INV-PII-3", "INV-PII-4"),
    "INV-LEDGER": ("INV-LEDGER",),
}


def invariant_manifest() -> dict[str, tuple[str, ...]]:
    """Return the INV → test node-id map (docs/55 §4)."""
    return dict(INVARIANT_MANIFEST)


def family(prefix: str) -> tuple[str, ...]:
    """The required invariant members of a family (e.g. ``"INV-SM"``)."""
    return REQUIRED_INVARIANTS.get(prefix, ())


def unmapped(required: tuple[str, ...],
             manifest: dict[str, tuple[str, ...]] | None = None) -> list[str]:
    """Return the required invariants that have NO mapped test (docs/55 §4). A MUST here
    blocks the phase-exit gate."""
    m = INVARIANT_MANIFEST if manifest is None else manifest
    return [inv for inv in required if not m.get(inv)]
