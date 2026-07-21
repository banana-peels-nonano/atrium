# Projections (S13) — RISKS
Owner: A10 Conductor Agent

## Risk register
| # | Risk | Likelihood | Impact | Category | Mitigation | Enforced |
|---|---|---|---|---|---|---|
| R1 | A projection quietly becomes a source of truth (someone reads a brief instead of the ledger to decide state) | medium | high | architectural-integrity | projections carry derived data only; the `gate` command acts via S5 on the LEDGER's venture, never on brief fields; purity tests prove regenerability | code + tests |
| R2 | Hidden state/caching makes two reads disagree | low | high | correctness | pure functions, no module globals; recompute + snapshot/restore identity tests | tests (purity pair) |
| R3 | A schema-broken Gate Brief (missing critic) reaches the founder | low | critical | governance | `critic` is a required constructor field; `NoCriticForGate` fail-closed; kill-day lists unbriefables explicitly | code-by-construction + tests (INV-COND-2) |
| R4 | Wall-clock leakage makes briefs nondeterministic | medium | medium | correctness | time = event `active_time`/recorded day strings only; `day` is a caller argument; no `datetime.now` in `projections/` (static sweep) | code + A1-style scan |
| R5 | The recommendation heuristic gets treated as an enforced rule (advisory drift into authority) | medium | medium | ambiguity | documented advisory-only (API.md); the founder's `gate` decision is the only authority; heuristic internal/free to change | doc + conductor tests |
| R6 | Fold performance degrades at large ledgers (full scan per call) | medium | low | performance | acceptable at factory scale; folds are single-pass; incremental/live projections are a later internal optimization behind the frozen signatures | doc (this row) |

## Refactor-avoidance notes
- `events → dataclass` folds with pinned orderings: new projections are new pure
  functions; richer briefs are additive fields (docs/43 §7).
- The one INV-COND-2 refusal type (`NoCriticForGate`) is shared with S12 — no
  parallel vocabulary.

## Assumptions
- S4 replay/read are deterministic and chain-verified (ledger/API.md — verified).
- `artifact_produced` (additive, this branch) carries `critic_tier` stamped by S10's
  checkpoint (capabilities/API.md — verified).
- `gate_decision.critic_tier` is populated by S12's gate command (conductor/API.md,
  same branch).
