# BUILD TRACKER — Charter House

**Append-only build ledger** (docs/70 §3). Newest entries at the bottom. This file +
an always-green `main` are the complete resumable state of the build (docs/70 §9).
Each entry records: date, phase, workstream, action, and any interface-freeze unlocked.

Legend — actions: `START` · `CONTRACTS-CLEARED` · `MERGED` · `PHASE-EXIT` ·
`INTERFACE-FREEZE` · `BLOCKING-IMPOSSIBILITY`.

| Date | Phase | Workstream | Action | Notes / Unlocks |
|---|---|---|---|---|
| 2026-07-03 | 0 | A0 Scaffold | START | Repository foundation per docs/53 Phase 0. |
| 2026-07-03 | 0 | A0 Scaffold | MERGED | Tree per docs/31 (structure test green, 107 passed); 13 subsystem packages × 4 empty contract docs; .gitignore/.env.example/pyproject; uv 0.11.26 + pinned pytest 8.3.4; git init (main); merge gates wired (scripts/ci.ps1 + pre-commit hook). |
| 2026-07-03 | 0 | Phase 0 | PHASE-EXIT | Exit criteria met: disjoint subsystem ownership (any agent creates its files without touching another's); merge gates (docs/63) active. **HALT** — awaiting founder go-ahead before opening Wave 0. |
| 2026-07-04 | 1–2 | Wave 0 | START | Founder go-ahead. Opened contract stage for A1 (Environment/S2), A2 (Config/S3), A3 (Ledger+Registry/S4), A11 (Logging+Test/S14+S15). |
| 2026-07-04 | 1–2 | Wave 0 | CONTRACTS-CLEARED | 20 contract docs + docs/WAVE0_CLEARANCE.md 56-consistency trace reviewed and **CLEARED by founder**. A1, A2, A3-Ledger, A3-Registry, A11 cleared to implement (tests-first, docs/70 §5). |
| 2026-07-04 | 1–2 | A3 Ledger/Registry (S4) | INTERFACE-FREEZE | **IF-1 frozen** (docs/52 §12): common envelope (docs/41 §1, verbatim in ledger/API.md) + event-type vocabulary (docs/41 §2) + `Ledger.append/read/replay/snapshot/restore` + `Registry.get/query`. **Unlocks A4 Lifecycle, A5 Governance/Security, A7 Memory.** Evolution: additive event types/fields = versioned no-bump; remove/rename/envelope-change = ICR (docs/43 §4). |
| 2026-07-04 | 1–2 | A2 Config (S3) | INTERFACE-FREEZE | **IF-2 (Config half) frozen**: `Config.get_route/get_model/get_provider/profile/budgets` + shared types Route/Model/Provider/Budgets (docs/40 §1). Router `LLMClient` half of IF-2 pending A6. **Unlocks A1 preflight, A6 Router (Config side).** |
| 2026-07-04 | 1–2 | A11 Logging/Test (S14+S15) | INTERFACE-FREEZE | Harness surface frozen: `Log.event`/`Telemetry.record` + fake signatures (InMemoryLedger == Ledger docs/40 §2) + invariant-manifest shape. Simulator shape-only (body deferred to S4/S5/S10/S12). |

---

## Open Blocking Impossibilities
_None._

## Interface freezes recorded
- **IF-1 — Ledger/Registry + Event catalog** (2026-07-04): envelope (docs/41 §1) + event vocabulary (docs/41 §2)
  + `append/read/replay/snapshot/restore` + `Registry.get/query`. Consumers: A4, A5, A7, A10, A11.
- **IF-2 (Config half)** (2026-07-04): `get_route/get_model/get_provider/profile/budgets` + Route/Model/Provider/Budgets.
  Router `LLMClient` half still pending A6.
- Pending: IF-2 (Router `LLMClient` half), IF-3 (Security redact/scan/tag), IF-4 (Lifecycle transition API), IF-5 (Workflow runner). See docs/43 §3.

## Current phase
**Phase 1–2 — Wave 0 implementation stage (CLEARED).** A1, A2, A3 (Ledger+Registry), A11 are cleared to
implement **tests-first** (docs/70 §5): write each `TESTPLAN.md` test, then implement to satisfy the `54`
acceptance rows + owned invariants, keeping docs in sync (docs/62), then open a PR against the 10 merge gates
(docs/63). IF-1 is frozen → A4/A5/A7 may begin their contract stage against Ledger stubs when scheduled.
Next halt: first Wave-0 merge gate, for founder review.
