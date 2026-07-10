# Lifecycle (S5) — RISKS
Owner: A4 Lifecycle Agent

## Risk register
- **R1 — Table drift from docs/42 §3.** The machine is only correct if the code table is
  the doc table. *Likelihood:* medium (25 rows, easy to mistype). *Impact:* critical
  (wrong legality = corrupted portfolio). *Category:* architectural-integrity.
  *Mitigation:* the table lives in one data structure; `test_table_matches_docs42_verbatim`
  pins the row set, auth kinds, and express markings 1:1; any doc change breaks the test
  first. *Enforced in:* code (`table.py`) + test.
- **R2 — Pivot is a multi-event sequence over a single-event append API (not atomic).**
  A crash between `kill` and `capture` leaves a killed venture with no fork.
  *Likelihood:* low. *Impact:* major (manual repair). *Category:* architectural-integrity.
  *Mitigation:* all checks run before the first append (refusal is all-or-nothing);
  ordering puts `kill` first so a torn sequence is a plain kill (safe, re-forkable — the
  lineage walk keys on `pivot_fork`, which is the *last* irreversible marker before
  capture); recovery = re-run pivot. Same acceptance shape as A3's non-atomic `restore`
  (ledger/RISKS.md finding 3) — documented for the hardening pass. *Enforced in:*
  code order (`pivot.py`) + doc.
- **R3 — Guard facts are only as honest as the acting subsystems.** S5 trusts
  `evidence_gate`/`spec_approved`/`partners` events at face value; a buggy producer could
  fake a PASS. *Likelihood:* low (producers are gated + tested). *Impact:* major.
  *Category:* ambiguity/security. *Mitigation:* facts must be *ledger* events (hash-
  chained, tamper-evident, PII-scanned on append); gate rows still require the founder's
  RED token, so no fact alone advances a venture. *Enforced in:* design (ledger-only
  facts) + S4 chain verification.
- **R4 — Clock unit ambiguity (active-days vs seconds).** Mixed units would corrupt every
  deadline. *Likelihood:* medium. *Impact:* major. *Category:* ambiguity. *Mitigation:*
  one unit (integer active-days) declared in IMPLEMENTATION §6.4 and typed through
  `ActiveTime`; Gov's separate seconds-based token clock never crosses the seam (tokens
  carry their own clock). *Enforced in:* code (types) + tests (INV-SM-3 set).
- **R5 — Slot race under concurrent transitions.** Two same-tick admissions could both
  see a free slot. *Likelihood:* low (single-founder, single-process design; docs/03).
  *Impact:* major. *Category:* architectural-integrity. *Mitigation:* slot check and
  append run inside one `transition` call over a `threading.Lock`-serialized Ledger
  append; slots are recomputed per call, never cached. A cross-process advisory lock is
  noted for the hardening pass. *Enforced in:* code + property test (sequential model).
- **R6 — Lineage walk cost grows with ledger size.** `pivot`/`grant_omw`/guards re-read
  the ledger per call. *Likelihood:* certain. *Impact:* minor at factory scale (≤ dozens
  of ventures, thousands of events; docs/03 scale). *Category:* performance.
  *Mitigation:* accepted; nightly perf tier (docs/55 §1) watches replay/read latency;
  a projection cache is a later, ledger-derived optimization. *Enforced in:* doc.
- **R7 — Judgment-guard envelope could be mistaken for full enforcement.** A reader might
  assume S5 verifies "duplicate"/"steady state" semantically. *Likelihood:* medium.
  *Impact:* minor (process). *Category:* ambiguity. *Mitigation:* IMPLEMENTATION §6.2
  states the resolution; API.md §Guard facts lists exactly which guards are objective vs
  judgment; `test_judgment_kill_requires_reason` pins the envelope. *Enforced in:* doc + test.

## Refactor-avoidance notes (priority #4)
- The transition table is **data, not code** — future revisions (a v1.2 lifecycle) edit
  rows, not control flow; the verbatim-fidelity test makes any drift loud.
- Guards are named pure functions over a `Facts` bundle — new guard = new function +
  row reference; no facade change.
- IF-4 freezes only the four docs/40 §3 signatures + value shapes; pivot/OMW/pause are
  additive v1 notes, so the Conductor (S12) can bind to them without an interface bump.
- The `GovPort` protocol keeps S6 swappable and honors INV-COND-1's ownership discipline
  from the other side: S5 will never need rework when Gov internals change.
- No durable S5 state at all → S5 restarts are free, replay is the recovery story, and
  the A11 simulator can drive S5 with nothing but a ledger dir and a clock.

## Assumptions (must match partners' API.md)
- **S4 (merged):** `append` is atomic + totally ordered; events with `to_state` set drive
  the replay state fold; `state_entered_at`/`experiment_live_at`/`evidence_ttl_at`/
  `omw_granted`/`forked_from` are projected exactly as ledger/API.md documents; the
  once-per-lineage replay caps (`omw_grant`, `pivot_fork`) key on `venture_id`
  (A3 accepted finding — S5 owns the true lineage rule).
- **S6 (merged):** `authorize` consumes a valid token on ok, does not consume on denial,
  never raises on business grounds (returns `Decision`); `grant` exists (additive seam)
  for tests/Conductor to mint at the founder boundary; unknown actions classify RED.
- **S12 (future):** the Conductor appends the guard-fact events (evidence, spec,
  partners, salvage, experiment metrics) through the owning capabilities before calling
  `transition`, and carries founder tokens to gate calls. Until S12 exists, tests play
  the acting-subsystem role with the same event shapes.
- **A11 (future):** the shared harness will absorb `_a4_support` (clock, simulator,
  oracle) unchanged in shape.
