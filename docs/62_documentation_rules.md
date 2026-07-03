# 62 — DOCUMENTATION RULES (keeping code and docs in sync)
**Owner:** Program · **Status:** authoritative

## Principle
Docs and code never drift. A PR that changes behavior without updating the relevant IB/contract doc **fails the merge gate** (`63`). Documentation is part of Done (`54` global DoD clause 6).

## The three doc layers and who keeps them current
1. **Implementation Bible (`docs/`)** — the frozen-architecture translation. Changes only via ICR (`43`) for interfaces, or Program for build-plan docs. Subsystem *behavior* docs (`10`–`33`) are updated when a subsystem's contract changes.
2. **Subsystem contract docs (`<module>/IMPLEMENTATION|API|TESTPLAN|RISKS.md`)** — owned by the subsystem agent; MUST match the code at merge time. `API.md` MUST match `40`.
3. **Code docstrings** — every public function documents signature, pre/postconditions, errors, determinism class, and (if action-triggering) authorization class.

## Sync checks (CI-enforced)
- `API.md` signatures == `40` == code signatures (a drift check compares them).
- Every `MUST`/`INV-*` referenced in a subsystem doc has a mapped test (`55` §4). An unmapped `MUST` fails the phase gate.
- Every event type in code exists in `41`; adding one requires updating `41` in the same PR (additive, versioned).
- The manifest ownership table (`00`) matches the actual file ownership; new files update it.

## Change-log discipline
- Interface changes carry an ICR id and a migration note (`43`).
- The Revision Register lineage (architecture v1.1) is preserved; if an implementation reveals a genuine impossibility, it is logged as a Blocking Impossibility (`70`), not a silent doc edit.

## Human-facing docs
- `README` and `05_founder_manual` obligations must remain accurate to what the software actually exposes (S12/S13). A change to a brief schema updates `05` + `40` + the projection code together.

## Definition of "documented"
A subsystem is documented when: its four contract docs exist and match code + `40`; its `MUST`s map to tests; its public API has docstrings; and the manifest/ownership/event catalog reflect it. Anything less blocks merge.
