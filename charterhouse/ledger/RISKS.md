# Ledger (S4) — RISKS
Owner: A3 Ledger/Registry Agent

## Risk register
| # | Risk | Likelihood | Impact | Category | Mitigation | Enforced in |
|---|---|---|---|---|---|---|
| R1 | A partial/torn write corrupts the append-only log (the single source of truth) | Med | Critical | architectural-integrity | write-then-commit + fsync; incomplete records never visible; ULID order independent of file layout | `test_partial_write_never_corrupts`, `test_append_atomic_ordered` |
| R2 | Silent tampering/edit of a historical event goes undetected | Low | Critical | security/integrity | `prev_hash` chain verified on read; replay refuses a broken chain (fail closed) | `test_tamper_detected_on_read`, `test_replay_refuses_broken_chain` |
| R3 | Raw PII/secret enters an event payload (bypassing S7 redaction) | Med | Critical | security | structural PII/secret pre-check at append (defense in depth); refs-only rule (docs/41 §4.4); CI secret scan | `test_reject_raw_pii_payload` + CI gate #6/#7 |
| R4 | `replay` is non-deterministic (ordering, hidden state), breaking `INV-LEDGER` | Med | Critical | architectural-integrity | replay is a pure fold over ULID-ordered events; no module-level mutable state (docs/61) | `test_replay_deterministic_state` (property) |
| R5 | Envelope drift: a consumer relies on a field A3 later renames, breaking A4/A5/A7 | Med | High | refactor/interface | envelope frozen verbatim at IF-1; changes require ICR + consumer sign-off (docs/43 §4) | clearance package + doc-sync gate |
| R6 | Catalog co-ownership with A7 causes an ownership/overlap conflict | Med | Med | architectural-integrity | A3 freezes envelope+vocabulary+append; A7 only emits pre-catalogued events + owns their payload semantics (IMPLEMENTATION §6) | ownership check (docs/60) |
| R7 | Once-per-lineage caps (`omw_grant`/`pivot_fork`) not enforced, corrupting lineage accounting | Low | High | correctness | replay-checked caps; S5 enforces the guard on top | `test_omw_grant_cap_replay_checked`, `test_pivot_fork_cap_replay_checked` |
| R8 | Backup/restore does not reproduce identical state (silent divergence) | Low | High | reliability | restore verifies chain; `restore(); replay()` byte-identical test | `it_snapshot_restore_replay_identical` |

## Refactor-avoidance notes
- **IF-1 is the load-bearing freeze on the critical path** (docs/52 §9): A4, A5, A7, A10, A11 all build
  against the envelope + `append/read/replay`. Freezing the *envelope shape and event vocabulary* (not the
  on-disk format) means the file layout can change freely later (segmentation, compression) with zero consumer impact.
- Event evolution is **additive-by-default** (`schema_version`); only removals/renames are breaking. This lets
  new event types (e.g. future memory events) land without reopening IF-1 — directly serving priority #4.
- Shared types (`Event`, `WorldState`, `State`, event-type enum) live once in `charterhouse/contracts/` (docs/43 §6).

## Assumptions
- Upstream redaction (S7 at CHECKPOINT) has already removed PII before `append`; the structural pre-check is
  defense-in-depth, not the primary redactor (docs/24).
- A1's `EnvContext` supplies valid, writable `data/ledger/` and `K:\Backups` paths on K: (docs/23 discipline).
- Single-writer operation (solo operator, docs/32); no multi-writer coordination is required or provided.
- Classification of an action as gate/RED is S6's responsibility; the Ledger validates only *presence* of
  `authorization` when the event type requires it (matches A5 `API.md`).
