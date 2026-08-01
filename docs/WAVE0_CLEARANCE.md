# Wave 0 — Contract-Stage Clearance Package
**Status: AWAITING FOUNDER CLEARANCE.** No implementation code exists. This is the `56`/`70 §4`
consistency check for A1 (Environment), A2 (Config), A3 (Ledger + Registry), and A11 (Logging/Test),
presented so clearance is mechanical, not a judgment call.

A subsystem is **CLEARED** when: (1) its four contract docs exist; (2) the `56` consistency check passes
(every API has a test; every risk has a mitigation; every source `MUST`/`INV-*` is traced into
IMPLEMENTATION + TESTPLAN; no unresolved ambiguity); (3) consumed interfaces match partners' frozen `API.md`.

---

## 1. Deliverables (20 docs)
| Subsystem | Folder | Docs |
|---|---|---|
| A2 Config (S3) | `charterhouse/config/` | IMPLEMENTATION · API · TESTPLAN · RISKS |
| A3 Ledger (S4) | `charterhouse/ledger/` | IMPLEMENTATION · API · TESTPLAN · RISKS |
| A3 Registry (S4) | `charterhouse/registry/` | IMPLEMENTATION · API · TESTPLAN · RISKS |
| A1 Environment (S2) | `charterhouse/env/` | IMPLEMENTATION · API · TESTPLAN · RISKS |
| A11 Logging/Test (S14+S15) | `charterhouse/logging/` | IMPLEMENTATION · API · TESTPLAN · RISKS |

## 2. Invariant / MUST → test trace (the acceptance half)
| Subsystem | INV / MUST (source) | Traced in IMPLEMENTATION | Test (TESTPLAN) |
|---|---|---|---|
| Config | `INV-CFG` clause 1 route→model (25 §4) | §2 | `test_invcfg_route_references_absent_model` |
| Config | `INV-CFG` clause 2 model→provider (25 §4) | §2 | `test_invcfg_model_references_absent_provider` |
| Config | unknown-key rejection (25 §4) | §2 | `test_unknown_key_rejected_located` |
| Config | profile-switch zero-code (54 §S3) | §2 | `test_profile_switch_reroutes_no_code_change` |
| Config | secrets-are-names-only (24) | §1/§6 | `test_get_provider_exposes_key_env_not_secret` |
| Config | env-boundary (20) | §6 | `test_no_env_read` |
| Ledger | `INV-LEDGER` state==replay (32/54 §S4) | §2 | `test_replay_deterministic_state` (property) |
| Ledger | atomic+ordered append (54 §S4) | §2 | `test_append_atomic_ordered`, `_partial_write_`, `_concurrent_` |
| Ledger | tamper-evidence, fail-closed (32) | §2 | `test_tamper_detected_on_read`, `_replay_refuses_broken_chain` |
| Ledger | snapshot→restore identical (54 §S4) | §3 | `it_snapshot_restore_replay_identical` |
| Ledger | no raw PII in payload `INV-PII-1` (41 §4.4) | §2 | `test_reject_raw_pii_payload` |
| Ledger | token id on gate/RED (41 §4.2) | §2 | `test_reject_gate_event_without_token` |
| Ledger | once-per-lineage caps (41 §4.3) | §2 | `test_omw_grant_cap_replay_checked`, `_pivot_fork_` |
| Ledger | schema_version evolution (41 §5) | §2 | `test_schema_version_stamped_and_read` |
| Registry | `INV-LEDGER` Registry==replay (54 §S4) | §2 | `test_registry_equals_replay` (property) |
| Registry | projection-only, no 2nd truth (41 §3) | §2 | `test_projection_only_no_mutation`, `_cache_rebuilds_` |
| Registry | fail-closed on chain break | §5 | `test_chain_break_fails_closed` |
| Environment | env-boundary: no env read outside `env/` (20) | §2 | `test_no_direct_env_read_outside_env` (static) |
| Environment | K:-discipline refuse off-K: write (23) | §2 | `test_offK_growing_write_refused` |
| Environment | one-precise-error per prereq (20/21) | §2 | all `*_one_error` tests |
| Environment | no partial boot `INV-FAILCLOSED` (61) | §2 | `test_no_partial_boot` |
| Environment | zero-paid on `free` (20) | §2 | `test_free_profile_zero_paid` |
| Logging/Test | `INV-TEST-SAFE` no real side effects (55 §6) | §2 | `test_test_safe_guard_blocks_real_action` |
| Logging/Test | no secret/PII in logs (24/54 §S14) | §2 | `test_log_strips_secret_fields`, `_pii_fields` |
| Logging/Test | invariant-harness completeness (55 §4) | §2 | `test_invariant_manifest_flags_unmapped_must` |
| Logging/Test | fake↔real parity (43) | §2 | `test_inmemory_ledger_signature_parity` |
| All four | `INV-DET` deterministic, no LLM import (61) | each §2 | anti-coupling import check (A11, static) |

**Coverage claim:** every source-spec `MUST`/`INV-*` owned by these four subsystems is traced into both
IMPLEMENTATION and TESTPLAN. No row is left with "demonstrated by a human" only (docs/54 global DoD).

## 3. Interface consistency (consumed ↔ exposed match)
| Consumer | Consumes | Provider's frozen `API.md` | Match |
|---|---|---|---|
| A1 Environment | `Config.load(config_dir, profile)`, `Config.get_route(role)` | Config `API.md` (docs/40 §1) | ✅ signatures identical; A1 injects env-derived params (no cycle) |
| A11 Telemetry | `Ledger.append(llm_call)` | Ledger `API.md` (docs/40 §2/§10) | ✅ `llm_call` in catalog (docs/41 §2) |
| A11 InMemoryLedger fake | *is* the `Ledger` signature | Ledger `API.md` (docs/40 §2) | ✅ parity asserted by `test_inmemory_ledger_signature_parity` |
| A3 Registry | `Ledger.replay/read` | Ledger `API.md` | ✅ same subsystem |
| All | shared types (`Route/Model/Provider/Budgets/Event/Venture/State/WorldState/EnvContext`) | `charterhouse/contracts/` (docs/43 §6) | ✅ single definition, no redefinition |

No consumer references a signature that isn't in a partner's frozen `API.md`.

## 4. Resolved ambiguities (no open questions remain)
- **Config reads no env; A1 injects `(config_dir, profile)`** → breaks the A1↔A2 cycle, honors docs/20. (Config §6, Env §6)
- **Config exposes `key_env` names, never secret values** → honors docs/24. (Config §6)
- **Ledger physical format = JSONL segments; ULID order independent of file layout.** (Ledger §6)
- **Event catalog co-ownership A3/A7:** A3 freezes envelope + vocabulary + append; A7 later emits pre-catalogued
  memory events and owns their payload semantics; new event types are additive, not an envelope change. (Ledger §6)
- **Registry owns no slot/WIP rules** (S5 does); it reflects replayed states only. (Registry §6)
- **A11 contract set covers S14+S15; `tests/` carries no separate contract docs** (not a `charterhouse/` subsystem folder). (Logging §6)
- **Lifecycle simulator: interface/shape frozen now, body deferred** to S4/S5/S10/S12 — not over-promised. (Logging §6)

## 5. Interface freezes requested — **ON YOUR CLEARANCE ONLY**
These are **not** recorded yet. On your approval they get appended to `docs/BUILD_TRACKER.md`:
- **IF-1 — Ledger/Registry + Event catalog (docs/52 §12):** the common envelope (docs/41 §1, reproduced verbatim
  in `ledger/API.md`), the event-type vocabulary (docs/41 §2), and `append/read/replay/snapshot/restore` +
  `Registry.get/query`. **Unlocks A4 Lifecycle, A5 Governance/Security, A7 Memory.** (The flagged, load-bearing freeze.)
- **IF-2 (Config half) — Config surface frozen:** `get_route/get_model/get_provider/profile/budgets`. (Router `LLMClient` half of IF-2 comes with A6.)
- **A11 harness surface** frozen so every subsystem tests into a stable harness.

## 6. What is explicitly NOT done (correct per instruction)
- No implementation code. No test bodies (TESTPLANs specify them; they are written at the implementation stage).
- No freeze recorded in the Build Tracker. No Wave-1 subsystem started.
- CI gate 1 (architecture/API check) is still a placeholder; **this document is the manual `56` clearance** it will later automate.
  *(Historical record, true as written on 2026-07-04. Gate 1 went live at Phase-7 exit on 2026-07-22 —
  `scripts/architecture_check.py` now enforces contract-doc liveness + docs/40 surface resolution mechanically.)*

## 7. Requested decision
**Clear A1, A2, A3, A11 to implement?** On "yes": I record CLEARED + IF-1 + Config-IF-2 in the Build Tracker and
begin the implementation stage (tests-first, per docs/70 §5) — stopping again for your review at the first merge gate.
