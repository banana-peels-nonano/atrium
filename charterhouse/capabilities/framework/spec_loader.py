"""S10 neutral capability-spec loader (capabilities/API.md §loader; docs/13).

Parses the frozen ``agents/*.agent.md`` contract FORMAT: required ``##`` sections
``Mission`` / ``Scope`` / ``Inputs`` / ``Outputs`` / ``Memory Scope`` (READ:/WRITE: tag
lists) / ``Escalation``, plus the mandatory literals "no authority" and "stateless"
anywhere in the document. Contracts, not prompts — A9 fills the six real specs in
Phase 5 against this parser (IF-5 unlock). Fail closed: any missing piece →
``SpecInvalid`` naming it; the empty Phase-0 stubs fail loudly, never silently.

Determinism (docs/61 §INV-DET): pure text parsing; stdlib only; no LLM, no env read.
"""

from __future__ import annotations

import re
from pathlib import Path

from charterhouse.capabilities.framework.types import CapabilitySpec, SpecInvalid

__all__ = ["load_capability_spec", "load_capability_specs"]

REQUIRED_SECTIONS = ("Mission", "Scope", "Inputs", "Outputs", "Memory Scope",
                     "Escalation")
REQUIRED_LITERALS = ("no authority", "stateless")

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _sections(text: str) -> dict[str, str]:
    """``## Heading`` → body text (verbatim, stripped)."""
    out: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[m.group(1)] = text[m.end():end].strip()
    return out


def _items(body: str) -> tuple[str, ...]:
    """A ``- item`` list → tuple; a bare paragraph → one-item tuple."""
    bullets = tuple(line[2:].strip() for line in body.splitlines()
                    if line.strip().startswith("- "))
    return bullets if bullets else ((body.strip(),) if body.strip() else ())


def _scope_tags(body: str, prefix: str, path: Path) -> tuple[str, ...]:
    """The ``READ:``/``WRITE:`` comma-separated tag list from the Memory Scope body."""
    for line in body.splitlines():
        line = line.strip()
        if line.upper().startswith(prefix + ":"):
            raw = line.split(":", 1)[1]
            return tuple(t.strip() for t in raw.split(",") if t.strip())
    raise SpecInvalid(f"{path.name}: Memory Scope section is missing its "
                      f"'{prefix}:' tag list")


def load_capability_spec(path: str | Path) -> CapabilitySpec:
    """Parse ONE neutral spec file. The capability ``name`` is the filename stem minus
    the ``.agent`` suffix (``scout.agent.md`` → ``scout``)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    sections = _sections(text)
    for required in REQUIRED_SECTIONS:
        if required not in sections or not sections[required].strip():
            raise SpecInvalid(f"{path.name}: missing required section '{required}' "
                              "(docs/13 neutral contract format)")
    lowered = text.lower()
    for literal in REQUIRED_LITERALS:
        if literal not in lowered:
            raise SpecInvalid(f"{path.name}: missing the mandatory '{literal}' "
                              "declaration (docs/13 — contracts, not prompts)")
    name = path.stem
    if name.endswith(".agent"):
        name = name[: -len(".agent")]
    return CapabilitySpec(
        name=name,
        mission=sections["Mission"],
        scope=sections["Scope"],
        inputs=_items(sections["Inputs"]),
        outputs=_items(sections["Outputs"]),
        memory_read=_scope_tags(sections["Memory Scope"], "READ", path),
        memory_write=_scope_tags(sections["Memory Scope"], "WRITE", path),
        escalation=sections["Escalation"],
    )


def load_capability_specs(agents_dir: str | Path) -> tuple[CapabilitySpec, ...]:
    """Parse every ``*.agent.md`` under ``agents_dir`` (sorted by name — deterministic).
    Strict per file: one invalid spec fails the whole load (fail closed)."""
    agents_dir = Path(agents_dir)
    return tuple(load_capability_spec(p)
                 for p in sorted(agents_dir.glob("*.agent.md")))
