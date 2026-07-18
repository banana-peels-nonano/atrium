"""S10 OpenCode harness adapter — the deterministic GENERATOR (docs/13 deliverable;
docs/30 "generators"; capabilities/API.md).

Neutral ``CapabilitySpec``s → OpenCode agent-definition markdown (YAML frontmatter +
contract body) under ``adapters/harness/opencode/``. Byte-deterministic (same specs →
same files), every file stamped GENERATED-DO-NOT-EDIT. It never invokes the harness and
never calls a model — harness files are DERIVED; the neutral specs in ``agents/`` stay
the single source of truth (harness-neutrality; RISKS R8). claude-code/aider generators
are later additive siblings.

Determinism (docs/61 §INV-DET): pure text generation; stdlib only; no LLM, no env read.
"""

from __future__ import annotations

from pathlib import Path

from charterhouse.capabilities.framework.types import CapabilitySpec

__all__ = ["generate_opencode", "GENERATED_STAMP"]

GENERATED_STAMP = "GENERATED-DO-NOT-EDIT"


def _render(spec: CapabilitySpec) -> str:
    """One OpenCode agent file: YAML frontmatter + the neutral contract body."""
    first_line = spec.mission.splitlines()[0].strip()
    lines = [
        "---",
        f"# {GENERATED_STAMP} — derived from agents/{spec.name}.agent.md "
        "(the neutral spec is the single source of truth)",
        f"description: {first_line}",
        "mode: subagent",
        "---",
        "",
        f"# {spec.name} — capability contract (generated for OpenCode)",
        "",
        "## Mission",
        spec.mission,
        "",
        "## Scope",
        spec.scope,
        "",
        "## Inputs",
        *(f"- {item}" for item in spec.inputs),
        "",
        "## Outputs",
        *(f"- {item}" for item in spec.outputs),
        "",
        "## Memory Scope",
        f"READ: {', '.join(spec.memory_read)}",
        f"WRITE: {', '.join(spec.memory_write)}",
        "",
        "## Escalation",
        spec.escalation,
        "",
        "This capability has no authority and is stateless: it cannot send, spend, "
        "deploy, or cross a gate.",
        "",
    ]
    return "\n".join(lines)


def generate_opencode(specs: tuple[CapabilitySpec, ...] | list[CapabilitySpec],
                      out_dir: str | Path) -> list[Path]:
    """Write one ``<name>.md`` per spec (sorted by name) into ``out_dir``; return the
    written paths. Overwrites cleanly on regeneration (drift shows as a diff)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for spec in sorted(specs, key=lambda s: s.name):
        path = out_dir / f"{spec.name}.md"
        path.write_text(_render(spec), encoding="utf-8", newline="\n")
        written.append(path)
    return written
