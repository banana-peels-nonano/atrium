# Governance (S6) — RISKS
Owner: A5 Governance/Security Agent

## Risk register
| # | Risk | Likelihood | Impact | Category | Mitigation | Enforced in |
|---|---|---|---|---|---|---|
| R1 | A RED action executes without (or with a stale/foreign) founder token — the core governance failure | Low | Critical | security | authorize is the single chokepoint: issued-here ∧ unexpired ∧ unconsumed ∧ scope ∧ venture all required; unknown actions denied outright | `test_red_requires_valid_scoped_token`, `test_classify_unknown_action_fail_closed`, property |
| R2 | Token replay: a captured token id re-authorizes a second action | Low | Critical | security | single-use consumption in the store on success; reuse refused; consumption state never on the (copyable) dataclass | `test_token_single_use_reuse_refused` |
| R3 | Envelope drift: memory-held totals diverge from reality (double-spend after crash/restart) | Med | High | architectural-integrity | cap/total are a pure fold over ledger events, recomputed per call; no cached accounting | `test_envelope_state_survives_restart`, property |
| R4 | Process-local token store: a restart voids granted-but-unused tokens | Med | Low | reliability (errs closed) | accepted by design — an unknown token is *invalid*, so the failure direction is a re-grant, never an unauthorized action; envelope/send accounting is ledger-derived and unaffected | IMPLEMENTATION §5 |
| R5 | Authorize→append gap: a granted `send.stage` not yet appended isn't counted against the day's budget (TOCTOU over-send) | Med | Med | correctness | single-operator, single-Conductor serialization makes the window trivial; budget re-checked at authorize time; documented for the S12 Conductor to serialize sends | IMPLEMENTATION §6; revisit at S12 |
| R6 | Class-matrix drift: a new Conductor command lands unclassified and runs autonomously | Med | Critical | security | unknown names classify RED **and** are denied; adding a command requires an explicit matrix entry + test | `test_classify_unknown_action_fail_closed`, `test_classify_matrix_frozen` |
| R7 | `send_batch` day attribution: events stamped near midnight could count against the wrong day's budget | Low | Low | correctness | day = envelope `timestamp` date (single injected clock); founder-wide cap makes ±1-day attribution a bounded error; deterministic in tests | `test_send_budget_day_rollover` |
| R8 | Two-key check spoofing: a `CheckResult(passed=True)` can be fabricated by the caller | Med | High | security | in-scope check is *presence + result* (S6 is the decision chokepoint, not the check runner); the automated check itself is owned by the deploy pipeline (S8/S12) and its ref is recorded in the action event for audit | `test_two_key_requires_token_and_check`; revisit at S12 |
| R9 | Additive surfaces (`grant`, `record_override`) read as frozen-interface creep | Low | Med | refactor/interface | documented as additive-no-bump (docs/43 §7) with version notes in API.md; the five docs/40 §4 signatures are untouched | API.md stability section |

## Refactor-avoidance notes
- The **matrix is data, not code** (`classify.py` table): new commands/classes are one-line
  additions with a test, never a control-flow rewrite.
- All accounting (envelope, send budget) is **derived from the ledger**, so persistence,
  crash-recovery, and audit come free from S4's guarantees; nothing here needs a migration if the
  storage layer changes.
- Gov performs no action — the enforcement seams (`authorize` before act, token id in the event's
  `authorization` field) are exactly the docs/40 §8 Conductor pipeline, so S12 can wire in without
  any S6 change (IF-3).
- `ConfigPort` protocol means swapping the FakeConfig for real S3 Config is a constructor argument,
  not a code change.

## Assumptions
- **Ledger (S4, per its API.md):** append is atomic/ordered; gate/RED-typed events require
  `authorization` presence; broken chain fails closed on read; `send_batch`/`spend_*` payloads
  round-trip verbatim.
- **Conductor (S12, future):** calls `classify` → (founder gate) → `grant`/`envelope_open` →
  `authorize` → acts → appends the action event carrying the consumed token id; serializes sends
  (R5). Holds no governance rule (INV-COND-1).
- **Security (S7, same agent):** payloads reaching Gov's appends are already redacted at
  CHECKPOINT; the Ledger's structural PII check is a backstop, not the primary control.
- **Config (S3, per frozen IF-2 shape):** `budgets.send_daily` is a non-negative int; the real
  Config will satisfy the same `ConfigPort` protocol the FakeConfig implements.
