# 32 — DATABASE (Ledger + Registry)
**Owner:** Ledger/Registry Agent (A3) · **Subsystem:** S4 · **Source of truth:** Memory Architecture (frozen), `41`

## Storage model (frozen)
The ledger is **append-only files** (not a server DB) on `K:\the_charter_house\data\ledger\`. This keeps the source of truth human-readable, git-friendly, backup-trivial, and dependency-free (consistent with the frozen "vault-as-repo, files-as-truth" decision). The Registry is a **projection** held in memory / a rebuildable index, never the source of truth.

## Ledger physical format
- Events are appended as ordered, immutable records (one event per line, e.g. JSONL, or one file per event — implementer chooses in `IMPLEMENTATION.md`, but MUST preserve total order + atomic append + hash chain).
- Each event carries `prev_hash` (chain integrity). Files are grouped by time or venture for scan efficiency; grouping MUST NOT affect global order (a monotonic `event_id`/ULID provides order).
- Rotation/segmentation is allowed for size; replay reads segments in order.

## Registry
- A record per venture (`42` §6). Built by `Ledger.replay()`; may be cached/indexed for speed but is always reconstructable.
- Queries (`Registry.query(state)`) power the portfolio-as-view and the board.

## MUST (`INV-LEDGER`)
- Append is atomic + totally ordered; a partial write never corrupts the log (write-then-commit / fsync discipline).
- `replay()` is deterministic: `Registry == replay(events)` for any event sequence (property test).
- Tamper-evident: altering a historical event breaks the hash chain, detected on read; replay refuses a broken chain (fail closed).
- No PII/secret in any event (redaction upstream; `INV-PII-1`).

## Backup/restore
`snapshot()` → dated `K:\Backups` copy of ledger (+vault+vectors); `restore()` + `replay()` reproduces identical registry state. CRITICAL backup class.

## Concurrency
Single-writer (append serialized). Solo-operator; no multi-writer coordination needed. Reads are lock-free over immutable segments.

## Acceptance
`54` S4: append/read/replay; concurrent-append ordering; hash-break detection; snapshot→restore→replay identical.
