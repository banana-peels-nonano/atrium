# 70 — CLAUDE CODE EXECUTION PLAN
## Exactly how Claude Code consumes and executes this package
**Owner:** Program · **Source of truth:** all IB docs · **Status:** authoritative · **This is the operating manual for the build.**

> This document assumes the environment is **"Claude Code Ready"** (Environment Spec Part 10). Claude Code acts as the **orchestrator** of the implementation agents (`51`), not as one monolithic programmer. Its job is to schedule agents, enforce gates, and keep the architecture invariant.

---

## 1. What Claude Code reads first (bootstrapping)
In order, once, before doing anything:
1. `README.md` → `00_manifest.md` → this doc (`70`).
2. The invariants it must never break: `02_doctrine.md`, `42_state_machine.md`, `14_governance.md`, `24_security.md`, `43_interfaces.md`.
3. The plan: `50_engineering_decomposition.md` → `52_dependency_graph.md` → `53_build_phases.md`.
4. The pre-code obligation: `56_contract_templates.md`.
Claude Code does **not** start coding after reading. It starts by **producing contracts** (§4).

## 2. Which implementation agent starts first
**A0 Scaffold**, alone. Nothing else can proceed until the repository skeleton + empty contract docs + CI + merge gates exist (Phase 0). When A0's exit criteria (`53` Phase 0) pass, Claude Code opens Wave 0 in parallel: **A1 (Environment), A2 (Config), A3 (Ledger/Registry), A11 (Test/Logging)**.

## 3. How work is scheduled (the loop Claude Code runs)
Claude Code maintains a **Build Tracker** (a ledger-style file, `docs/BUILD_TRACKER.md`, append-only) and runs this loop:
```
loop:
  1. Read Build Tracker → determine current phase + completed workstreams.
  2. From 52 dependency graph → compute the set of UNBLOCKED workstreams
     (all their upstream interface-freezes are recorded as done).
  3. For each unblocked workstream, in priority order:
       a. If its 4 contract docs (56) are not CLEARED → run the contract stage (§4).
       b. Else → run the implementation stage (§5).
  4. When a workstream passes its merge gate (63) → record completion + any
     interface-freeze (52 §12) it unlocks in the Build Tracker.
  5. If a phase's exit criteria (53) are all met → advance the phase.
  6. Repeat until Phase 9 exit criteria pass → Charter House is operable.
```
Parallelism: Claude Code may progress multiple unblocked workstreams; because ownership is disjoint (`60`) and dependencies are on interfaces (`43`), they do not conflict. The critical path (`52` §9) is prioritized.

## 4. Contract stage (per subsystem — BEFORE any code)
For each subsystem, the owning agent produces its four docs from the templates (`56`): `IMPLEMENTATION.md`, `API.md`, `TESTPLAN.md`, `RISKS.md`. Claude Code runs the **consistency check** (`56`): every API has a test; every risk has a mitigation; every source-spec `MUST`/`INV-*` is traced into IMPLEMENTATION + TESTPLAN; no unresolved ambiguity. Only when the four are consistent and its consumed interfaces match partners' frozen `API.md` does the subsystem become **CLEARED** (recorded in the Build Tracker). This is the primary rewrite-prevention gate.

## 5. Implementation stage (per subsystem)
1. Build against **frozen interfaces** (`40`/`43`); stub not-yet-built partners from their `API.md` (`43` §2).
2. Write the `TESTPLAN.md` tests first (or alongside), using the shared fakes (`55` §2). No functionality without a validation path.
3. Implement to satisfy the tests + the `54` acceptance rows + all owned `INV-*`.
4. Keep docs in sync (`62`) in the same change.
5. Open a PR with the 10-gate checklist (`63`); a different context/Program reviews; the invariant-harness report is attached.
6. On green merge, record completion + unlocked interface-freezes.

## 6. How agents communicate
- **Only through frozen interfaces** (`40`/`43`) and the **Build Tracker** (append-only status). No agent reaches into another's internals.
- Interface changes go through the **ICR** protocol (`43` §4) — never a silent edit.
- Shared types live once in `contracts\`. Cross-subsystem needs are resolved by interface, not by copying code.

## 7. How merge requests occur
Per `63`: short-lived `feat/<subsystem>-<task>` branch → PR with the 10-gate checklist → different-vantage review (mirrors the runtime Critic) → all 10 gates green (including invariant harness, PII, determinism, ownership) → squash-merge to always-green `main`. No gate overrides.

## 8. How failures are handled
- **Test/gate failure:** the workstream stays open; fix and re-run. Never merge red.
- **Model/provider failure during a build task:** Claude Code retries; this is a build-tooling issue, unrelated to the product's runtime failover.
- **Ambiguity in a spec:** first attempt to resolve from the frozen docs + this IB. If genuinely under-specified, record a **Resolution** in the subsystem `IMPLEMENTATION.md` §6 and proceed with the most invariant-preserving reading (`01` tie-breaker). Do NOT redesign.
- **Blocking Impossibility (rare):** if a spec is *physically un-implementable* (not merely inconvenient), halt that workstream, write a Blocking Impossibility entry in the Build Tracker (what, why physically impossible, minimal options), and escalate to Program/the human. This is the ONLY path that can touch architecture, and only with human sign-off (`00` §4).

## 9. How implementation resumes after interruption
State lives in `main` (always green) + the Build Tracker (append-only). To resume:
1. Read the Build Tracker → last completed workstreams + current phase + any open Blocking Impossibility.
2. Recompute unblocked workstreams from `52`.
3. Continue the loop (§3). Because branches are short-lived and `main` is green, there is no divergent state to reconcile — resumption is deterministic. (This mirrors the product's own crash→replay property.)

## 10. How architecture compliance is continuously verified
Compliance is **mechanical, not judgmental**:
- The **invariant harness** (`55` §4) maps every `INV-*` to a named test; CI reports red/green per invariant; a red invariant blocks merge.
- The **anti-coupling import check** (`43` §8) enforces the determinism boundary and subsystem seams.
- The **secret/PII scan** blocks any secret or raw-PII leak (`24`).
- The **doc-sync check** (`62`) blocks code/spec drift and `API.md`↔`40` drift.
- The **ownership check** (`60`) blocks cross-owner edits.
- The **lifecycle simulator** (`55` §3) reproduces Stress-Test A/B/C every relevant PR.
If all of these are green, the architecture is—by construction—preserved. That is the whole point of this Implementation Bible: turn "did we honor the design?" into a green build.

## 11. Definition of "Charter House implemented"
Phase 9 exit criteria pass (`53`): environment ready; deterministic spine proven; router + memory + capabilities integrated; governance + PII enforced end-to-end; Conductor runs a full venture dry-run Capture→Graduate with zero real spend/send/deploy; backup/restore verified; every `INV-*` green; docs synced. At that point the founder can operate Charter House per `05`. **Ship.**

---

## Appendix — the one-screen operating summary for Claude Code
```
READ: README→00→70→(02,42,14,24,43)→(50,52,53)→56
START: A0 scaffold (Phase 0) → then A1,A2,A3,A11 in parallel
PER SUBSYSTEM: contracts (56) → CLEARED → tests-first → implement to 54+INV → PR (63 10 gates) → merge → record unlock
SCHEDULE: Build Tracker + 52 DAG → always advance unblocked, prioritize critical path
NEVER: merge red · change a 40 signature without an ICR · embed/cloud-route PII · redesign architecture · advance a phase before its exit criteria
RESUME: read Build Tracker + green main → recompute unblocked → continue
DONE: Phase 9 exit criteria all green
```
