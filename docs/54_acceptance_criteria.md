# 54 — ACCEPTANCE CRITERIA & DEFINITION OF DONE
## Per-subsystem gates that a merge must satisfy
**Owner:** Program · **Source of truth:** subsystem docs + `42`/`14`/`24` invariants · **Status:** authoritative

> A subsystem is **Done** only when every row below is demonstrably true via an automated test in the harness (`55`). "Demonstrated by a human" is insufficient; the check must be repeatable in CI. These criteria are the acceptance half of each merge gate (`63`).

## Global Definition of Done (applies to every subsystem)
1. Four contract docs exist and are internally consistent (`56`).
2. Only owned files changed (`60`).
3. Unit + integration tests exist and pass; coverage of the subsystem's `MUST` clauses is 100%.
4. All referenced `INV-*` invariants have a passing test.
5. Public interface matches `43`; no undocumented API.
6. Docs updated in the same PR (`62`); no code/spec drift.
7. `61` standards pass (lint, types, determinism check).
8. No secret, no raw PII, no `*.private.md` content in the diff or logs.

## Per-subsystem acceptance

### S3 Config
- Valid config loads into an immutable typed object; unknown keys rejected with a located error.
- `INV-CFG`: every `routes.yaml` primary/fallback references a model present in `models.yaml`. **Test:** load a config with a dangling ref → rejected.
- Profile switch changes resolved routes with zero code change. **Test:** two profiles, same call, different model resolved.

### S4 Ledger & Registry
- `INV-LEDGER`: `current_state == replay(all_events)` for arbitrary event sequences (property test).
- Append is atomic and totally ordered; concurrent appends never interleave a record.
- Tamper detection: mutating any historical event breaks the hash chain and is detected on read.
- Snapshot→restore reproduces byte-identical state.

### S5 Lifecycle
- `INV-SM-1`: no illegal transition executes (full matrix test).
- `INV-SM-2`: WIP limits (validating ≤3, SHAPING =1, building ≤1, HARVEST alumni ≤3) never exceeded.
- `INV-SM-3`: deadlines computed in factory-active time from `experiment_live_at`; `pause` freezes clocks.
- `INV-SM-4`: express-advance rejected for slot-consuming transitions.
- `INV-SM-5`: pivot = kill-and-fork; second fork in a lineage refused (ledger-checked).
- `INV-SM-6`: evidence TTL enforced for shovel-ready before BUILDING.

### S6 Governance
- `INV-GOV-1`: every RED action without a valid token is refused.
- `INV-GOV-2`: two-key actions require token AND passing check.
- `INV-GOV-3`: tokens are single-use and expire; reuse refused.
- `INV-GOV-4`: spend within envelope is YELLOW; breach re-REDs.
- `INV-GOV-5`: send budget is founder-wide (≤ configured/day), allocated by priority; never per-venture-unbounded.
- `INV-GOV-6`: every founder override is logged with reason.

### S7 Security / PII
- `INV-PII-1`: redaction runs at CHECKPOINT before any embed or cloud route; raw PII goes only to `*.private.md`.
- `INV-PII-2`: deterministic scanner (no LLM) flags residual PII/secrets; CHECKPOINT fails closed on a hit.
- `INV-PII-3`: any `contains_pii` context is refused by every cloud adapter (tested with S8).
- `INV-PII-4`: `*.private.md` is gitignored and never embedded, logged, or pushed.

### S8 Router
- `INV-ROUTE-1`: role→model resolved from config only; no role logic in router.
- `INV-ROUTE-2`: primary failure → deterministic failover order; exhaustion → degrade to free/local → else `pause`.
- `INV-ROUTE-3`: PII-tagged context never routed to a cloud adapter.
- `INV-ROUTE-4`: telemetry records tokens/$/latency per call.

### S9 Memory
- `INV-MEM-1`: retrieval returns top-K only; Doctrine always included; retired/superseded excluded.
- `INV-MEM-2`: embedding model id is pinned; a change triggers a guarded full re-index, never silent.
- `INV-MEM-3`: consolidation is a reversible view; the ledger is never edited.
- `INV-MEM-4`: no PII embedded (joint with S7).

### S10 Capability Framework
- `INV-WF-1`: CHECKPOINT is the only state-mutating beat; PRODUCE/CRITIQUE are idempotent + retryable.
- `INV-WF-2`: CRITIQUE runs on a different model family; degrade ladder to deterministic tier-3 always available; tier recorded.
- `INV-WF-3`: no gate is presentable without an attached Critic take.

### S11 Capabilities
- Each capability's declared memory scope matches its contract (`13`); write outside scope is refused.
- No capability holds authority (cannot send/spend/deploy/cross a gate). **Test:** attempt → refused by framework.

### S12 Conductor & S13 Projections
- `INV-COND-1`: no rule owned by S5/S6/S7 is re-implemented in the Conductor (call-through verified by test).
- `INV-COND-2`: Gate Brief conforms to the fixed schema and includes the Critic field.
- `INV-COND-3`: crash mid-command → replay reconstructs state with no loss.
- Projections (PIPELINE/METRICS/briefs) are pure functions of the ledger (regenerable, deterministic).

### S14 Logging / S15 Testing
- Every subsystem emits structured logs; no secret/PII in logs.
- The lifecycle simulator reproduces Stress-Test A/B/C outcomes and the v1.1 revision behaviors.
