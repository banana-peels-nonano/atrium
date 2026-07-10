# Governance (S6) — TESTPLAN
Owner: A5 Governance/Security Agent   (written BEFORE implementation)

## Unit tests (`tests/unit/test_governance.py`, support in `tests/unit/_a5_support.py`)
| Test | Asserts | Fake(s) | Covers |
|---|---|---|---|
| `test_classify_matrix_frozen` | every docs/40 §8 command name maps to its documented GREEN/YELLOW/RED class; the two-key set is exactly {deploy.prod, billing.enable, scaled send.stage} | none (pure) | class matrix (docs/54 §S6) |
| `test_classify_unknown_action_fail_closed` | an unknown action name classifies RED; `authorize` denies it even with a token of matching scope | tmp ledger, FakeConfig | fail-closed classify |
| `test_green_yellow_need_no_token` | GREEN and YELLOW actions authorize ok with `token=None`; nothing consumed | tmp ledger, FakeConfig | class semantics |
| `test_red_requires_valid_scoped_token` | RED with `None`/forged (not issued here)/wrong-scope/wrong-venture token → denied with reason; valid grant → ok | tmp ledger, FakeConfig, fixed clock | **`INV-GOV-1`** |
| `test_token_single_use_reuse_refused` | a consumed token presented again → denied; denial does not consume a live token | fixed clock | **`INV-GOV-3`** |
| `test_token_expires` | advancing the injected clock past `expires_at` → denied; before expiry → ok | fixed clock | **`INV-GOV-3`** |
| `test_two_key_requires_token_and_check` | deploy.prod / billing.enable with valid token but missing or failing `CheckResult` → denied (token not consumed); token + passing check → ok | fixed clock | **`INV-GOV-2`** |
| `test_scaled_send_is_two_key` | send.stage with count > threshold classifies two-key and requires the check; small batch is plain RED | FakeConfig | **`INV-GOV-2`** |
| `test_scaled_send_malformed_count_fails_closed` | a send.stage `count` that is not a clean non-negative integer (string, bool, fractional, negative) classifies two-key and is denied by `authorize` (a denial, never an exception); the grant survives unconsumed | FakeConfig | **`INV-GOV-2/5`** fail-closed |
| `test_envelope_within_cap_yellow` | open $120 → spends 50, 40 ok with `color=YELLOW`; `spend_meter{amount_usd, running_total}` events appended with correct totals | tmp ledger | **`INV-GOV-4`** (R-ENVELOPE) |
| `test_envelope_degrade_past_80pct` | a spend crossing 80% of cap returns `degrade=True` (auto-degrade, docs/14) | tmp ledger | `INV-GOV-4` |
| `test_envelope_breach_re_red` | a spend pushing past cap → refused, `spend_breach{attempted, cap}` appended, headroom still spendable; a **fresh** `envelope_open` resets cap+total and spending resumes | tmp ledger | **`INV-GOV-4`** breach→re-RED |
| `test_spend_without_envelope_refused` | `spend` before any `envelope_open` → refused, nothing appended | tmp ledger | `INV-GOV-4` authorize-once |
| `test_envelope_state_survives_restart` | a second `Gov` over the same ledger sees the same cap/total (accounting is ledger-derived, not memory) | tmp ledger | `INV-GOV-4` + ledger-as-truth |
| `test_send_budget_founder_wide` | `send_daily=40`; authorized batches across 3 ventures totalling 40 → ok; the batch that would exceed remaining → denied (never per-venture-unbounded) | tmp ledger, FakeConfig | **`INV-GOV-5`** (R-SEND-BUDGET) |
| `test_send_budget_day_rollover` | next `day` → remaining resets to `send_daily`; floor 0 on over-count | tmp ledger, FakeConfig | `INV-GOV-5` |
| `test_override_logged_with_reason` | `record_override` appends `override{recommendation, decision, reason}` (and `score_override{old_score, new_score, reason}` for kind="score") | tmp ledger | **`INV-GOV-6`** (R-OVERRIDE-LOG) |
| `test_override_empty_reason_refused` | empty/whitespace reason → `MissingReason`, nothing appended | tmp ledger | `INV-GOV-6` fail-closed |
| `test_property_governance_oracle` (property, `seed` in `range(40)`) | for seeded random op sequences (grant/authorize/envelope_open/spend across ventures): no token ever authorizes twice; Σ metered spends per envelope ≤ cap; every engine accept/deny matches an independent accounting oracle | tmp ledger, FakeConfig, fixed clock | `INV-GOV-1/3/4` (property) |

## Integration tests (`tests/integration/test_governance_security.py`)
| Test | Partner | Scenario | Expected ledger/state |
|---|---|---|---|
| `test_it_stress_a_envelope_arc` | S4 Ledger (real) | the Venture-A $120 LinkedIn-boost arc (Stress Test §1/A3): open envelope, daily YELLOW spends, breach attempt, founder re-RED with a new envelope | event stream = `spend_envelope, spend_meter…, spend_breach, spend_envelope, spend_meter`; totals correct at every step |
| `test_it_redacted_payload_accepted_raw_rejected` | S7 Security + S4 Ledger | a payload built from `Sec.redact` output appends fine; the same payload with raw corpus PII is rejected by the Ledger's structural pre-check | defense-in-depth: S7 upstream, S4 backstop |

## Invariant coverage table
| INV / MUST | Test name | Tier |
|---|---|---|
| `INV-GOV-1` RED needs valid scoped token | `test_red_requires_valid_scoped_token`, `test_classify_unknown_action_fail_closed`, property | unit |
| `INV-GOV-2` two-key = token AND check | `test_two_key_requires_token_and_check`, `test_scaled_send_is_two_key`, `test_scaled_send_malformed_count_fails_closed` | unit |
| `INV-GOV-3` single-use + expiring | `test_token_single_use_reuse_refused`, `test_token_expires`, property | unit |
| `INV-GOV-4` envelope authorize-once / YELLOW / breach re-RED | `test_envelope_within_cap_yellow`, `test_envelope_degrade_past_80pct`, `test_envelope_breach_re_red`, `test_spend_without_envelope_refused`, `test_envelope_state_survives_restart`, property, `it_stress_a_envelope_arc` | unit + integration |
| `INV-GOV-5` founder-wide send budget | `test_send_budget_founder_wide`, `test_send_budget_day_rollover` | unit |
| `INV-GOV-6` overrides logged with reason | `test_override_logged_with_reason`, `test_override_empty_reason_refused` | unit |
| Class matrix (docs/54 §S6) | `test_classify_matrix_frozen`, `test_green_yellow_need_no_token` | unit |
| `INV-DET` (no LLM, deterministic) | anti-coupling import check (A11 gate 5/10; hand-verified until active) | static |

## Fixtures/fakes needed (from A11 shared harness; A5-local until A11 lands)
- **FakeConfig** (`_a5_support`) — a `ConfigPort` double returning a frozen
  `contracts.config_types.Budgets`; replaced by real S3 Config when A2 lands (same shape).
- **Fixed/steppable Clock** (`_a5_support`) — drives token expiry and `timestamp` days deterministically.
- **tmp-path real Ledger** — the merged S4 implementation on `tmp_path` (A3 convention); no in-memory fake needed.
- **PII corpus** (`tests/fixtures/pii_corpus.py`, shared with S7) — for the defense-in-depth integration test.
- **Seeded op-sequence generator + accounting oracle** (`_a5_support`) — the property test's independent re-derivation (never calls Gov internals).

## Out of scope (test-safety, INV-TEST-SAFE)
No real spend/send/deploy/charge is exercised anywhere: tests assert **up to the authorization
boundary** — token minting (`grant`/`envelope_open`), authorize/deny decisions, and ledger
records. No network, no provider call, no e-mail/DM send, no billing surface exists in S6 at all.
