# Projections (S13) — IMPLEMENTATION
Owner: A10 Conductor Agent   Subsystem: S13   Source of truth: docs/40 §9 + docs/41 §3 + docs/05 (brief shapes) + docs/54 §S13

## 1. Responsibility (one paragraph)
S13 renders the ledger for humans: the PIPELINE board, METRICS, the triaged Daily
Brief, the fixed-schema Gate Brief (critic mandatory), the Kill-Day Brief, and the
Calibration report — every one a pure, deterministic, regenerable function of the
event stream. It MUST NOT: be a source of truth (INV-COND-3 — deleting every
projection loses nothing), hold state or caches, read anything but the ledger, write
anything, call an LLM, or read the wall clock (time = event `active_time`).

## 2. Invariants enforced
- **INV-COND-2** — the Gate Brief schema + mandatory critic: `GateBrief.critic` is a
  required constructor field; `gate_brief()` raises `NoCriticForGate` when the
  venture's history holds no critic take. Kill-day never silently drops an
  unbriefable venture (named in `unbriefable`).
- **INV-COND-3 (S13 half)** — pure functions of the ledger: same events → identical
  values, twice, and across snapshot/restore/replay; regenerable from scratch.
- **INV-TRIAGE (docs/05)** — the Daily Brief is triaged; empty-decisions silence is a
  first-class output, not an error.

## 3. Internal design
Modules under `charterhouse/projections/`:
- `types.py` — the frozen dataclasses + `NoCriticForGate`.
- `board.py` — `pipeline` (replay + flags fold), `metrics` (single-pass event fold).
- `briefs.py` — `daily_brief`, `gate_brief`, `killday_brief` (built on `pipeline` +
  per-venture event folds; the mechanical recommendation heuristic lives here,
  advisory-only).
- `calibration.py` — `calibration` (override/evidence folds vs terminal outcomes).
All folds iterate `ledger.read()` once per call and derive everything; ties and
orderings are pinned (venture id asc, event order as appended).

## 4. Dependencies
S4 `Ledger.read/replay` + the frozen `Event`/`EventType`/`State` contracts. Nothing
else — S13 imports no other subsystem (the anti-coupling scan pins it).

## 5. Failure behavior
- No critic take for a requested gate brief → `NoCriticForGate` (fail closed — the
  brief does not exist rather than existing schema-broken).
- A broken chain/malformed ledger surfaces S4's typed errors unchanged.
- An unknown venture id → S4's lookup semantics (`None` → `NoCriticForGate`-adjacent
  typed refusal naming the venture).
- Everything else is total: empty ledgers yield empty boards/metrics/briefs
  (silence-valid).

## 6. Open questions → RESOLVED
1. **Where does the Gate Brief's critic come from?** RESOLVED: the venture's latest
   `artifact_produced.critic_tier` (the S10 checkpoint stamp), falling back to the
   latest `gate_decision.critic_tier` (a prior gate's take). None → refuse
   (INV-COND-2).
2. **Recommendation mechanics.** RESOLVED: advisory fold — KILL when the latest
   evidence/experiment verdict is FAIL or a TTL/window fact has lapsed; ADVANCE when
   the state's forward-guard facts all read PASS; HOLD otherwise. Heuristic is
   internal (free to tighten); the founder's `gate` decision is the authority.
3. **Does `daily_brief` need a clock for "today"?** RESOLVED: no wall clock — `day`
   is an optional caller argument (the Conductor passes it); absent, sends are
   grouped by their recorded day strings. Determinism preserved.
