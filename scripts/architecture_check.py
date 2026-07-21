"""Merge gate 1 — architecture contracts / ICR drift (docs/63 gate 1; docs/62 sync).

Two checks, both fail-closed:
1. **Contract docs live** — every subsystem package carries its four docs/56 documents
   and none is still the Phase-0 "STATUS: EMPTY" scaffold (contracts-before-code held).
2. **The docs/40 frozen surfaces exist in code** — every §1–§10 seam name resolves to a
   real attribute (import + hasattr). A vanished/renamed frozen name fails the gate:
   that is exactly the no-ICR drift docs/43 §4 forbids.

Scope note (honest): this verifies surface PRESENCE, not full signature equality — a
parameter-level drift check is docs/62's "lands with 62 tooling" follow-up. Presence
catches the breaking class of drift (remove/rename) mechanically.

Usage: python scripts/architecture_check.py   (exit 0 = gate passes)
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCAFFOLD_MARK = "STATUS: EMPTY"
CONTRACT_DOCS = ("API.md", "IMPLEMENTATION.md", "TESTPLAN.md", "RISKS.md")

# Subsystem packages that carry the four contract docs (docs/56).
DOC_PACKAGES = (
    "capabilities", "conductor", "config", "env", "governance", "ledger",
    "lifecycle", "logging", "memory", "projections", "registry", "router",
    "security",
)

# The docs/40 §1–§10 frozen seams: module → {attribute: (member, ...)}.
FROZEN_SURFACES: dict[str, dict[str, tuple[str, ...]]] = {
    "charterhouse.config": {
        "Config": ("load", "get_route", "get_model", "get_provider", "profile",
                   "budgets", "models", "memory"),
    },
    "charterhouse.ledger": {
        "Ledger": ("append", "read", "replay", "snapshot", "restore"),
    },
    "charterhouse.registry.facade": {"Registry": ("get", "query")},
    "charterhouse.lifecycle": {
        "Lifecycle": ("can_transition", "transition", "slots", "clock", "pivot",
                      "grant_omw", "pause", "resume"),
    },
    "charterhouse.governance": {
        "Gov": ("classify", "authorize", "envelope_open", "spend",
                "send_budget_remaining"),
    },
    "charterhouse.security": {
        "Security": ("redact", "scan", "tag", "checkpoint"),
    },
    "charterhouse.router.facade": {
        "Router": (), "LLMClient": ("call",),
    },
    "charterhouse.memory": {
        "Memory": ("retrieve", "write_lesson", "consolidate", "reindex"),
        "OllamaEmbedder": ("embed",),
    },
    "charterhouse.capabilities.framework": {
        "Workflow": ("run",), "Capability": ("produce",), "Critic": ("critique",),
        "WorkflowRegistry": (), "load_capability_spec": (),
        "generate_opencode": (),
    },
    "charterhouse.conductor": {"Conductor": ("command", "gate_brief")},
    "charterhouse.projections": {
        "pipeline": (), "metrics": (), "daily_brief": (), "gate_brief": (),
        "killday_brief": (), "calibration": (),
    },
    "charterhouse.logging": {"Log": ("event",), "Telemetry": ("record",)},
}


def main() -> int:
    failures: list[str] = []

    for pkg in DOC_PACKAGES:
        for doc in CONTRACT_DOCS:
            path = ROOT / "charterhouse" / pkg / doc
            if not path.is_file():
                failures.append(f"{pkg}/{doc}: missing contract doc (docs/56)")
            elif SCAFFOLD_MARK in path.read_text(encoding="utf-8"):
                failures.append(f"{pkg}/{doc}: still the Phase-0 scaffold (docs/56)")

    for module_name, surface in FROZEN_SURFACES.items():
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001 — any import failure IS drift
            failures.append(f"{module_name}: import failed ({type(exc).__name__})")
            continue
        for attr, members in surface.items():
            obj = getattr(module, attr, None)
            if obj is None:
                failures.append(f"{module_name}.{attr}: frozen docs/40 name missing")
                continue
            for member in members:
                if not hasattr(obj, member):
                    failures.append(
                        f"{module_name}.{attr}.{member}: frozen docs/40 member "
                        "missing (remove/rename requires an ICR, docs/43 §4)")

    if failures:
        print("[gate 1] architecture-contract drift:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"[gate 1] architecture contracts OK ({len(FROZEN_SURFACES)} modules, "
          f"{len(DOC_PACKAGES)}x4 contract docs live)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
