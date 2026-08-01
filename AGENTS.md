# AGENTS — harness-neutral constitution pointer

This file is the harness-neutral entry point for any coding agent (Claude Code,
OpenCode, or otherwise) working in this repository. It carries no rules of its own;
it points at the authoritative, frozen specification.

## Read first, in order (per `docs/70_claude_code_execution_plan.md` §1)
1. `docs/README.md` → `docs/00_manifest.md` → `docs/70_claude_code_execution_plan.md`
2. Invariants that must never break: `docs/02_doctrine.md`, `docs/42_state_machine.md`,
   `docs/14_governance.md`, `docs/24_security.md`, `docs/43_interfaces.md`
3. The plan: `docs/50_engineering_decomposition.md` → `docs/52_dependency_graph.md` →
   `docs/53_build_phases.md`
4. The pre-code obligation: `docs/56_contract_templates.md`

## The rules that override everything
- Architecture is immutable — implement as written; a *Blocking Impossibility* is the
  only path that touches architecture, and only with human sign-off (`docs/00` §4).
- Contracts before code; tests before implementation.
- Every merge passes all 10 gates in `docs/63`. Never merge red.
- One owner per file (`docs/60`). Determinism first; fail closed; never cloud-route PII.

## Current state
**Built and archived.** Every subsystem S2–S15 is real on an always-green `main`, all ten
`docs/63` merge gates are mechanically enforced, and the project is closed as a documented
learning artifact — see the top-level `README.md` for the final state and retrospective.
The append-only build ledger (every gate, every honest limit) is `docs/BUILD_TRACKER.md`.
