# Router (S8) — RISKS
Owner: A6 Router Agent

## Risk register
| # | Risk | Likelihood | Impact | Category | Mitigation | Enforced in |
|---|---|---|---|---|---|---|
| R1 | A PII-tagged context reaches a cloud provider (the single most dangerous hole, Stress-Test C3) | Low | Critical | security | **two independent layers**: chain filter (local-only candidates) + the merged S7 guard called inside every cloud adapter before any send; `pii_block` audit event | `test_pii_chain_excludes_cloud`, `test_cloud_adapter_hard_guard`, integration flow |
| R2 | Role logic creeps into the router (a "default role" or hardcoded model), breaking profile swappability | Med | High | architectural-integrity | the only role lookup is `Config.get_route`; unknown role propagates; profile-switch test pins zero-code rerouting | `test_role_resolved_from_config_only`, `test_unknown_role_propagates_config_error` |
| R3 | Failover order drifts (retry loops, reordering, racing), making incidents undebuggable | Med | Med | correctness | candidates tried strictly in config order, one attempt each; degrade extension deterministic (sorted, minus tried); seeded property test | failover tests + property |
| R4 | Secret values leak into S8 (env read or key in config), breaking docs/20/24 | Low | Critical | security | `key_env` stays a name; no `os.environ` in `router/` (A1 static boundary test); real transport takes injected `key_lookup` at wiring time — not shipped in A6 | A1 env-boundary test + CI secret scan |
| R5 | Budget fold undercounts (missing timestamps) → silent overspend | Med | Med | cost | conservative fold: un-timestamped `llm_call` events count toward the current month (degrade earlier, never overspend); cross-note for A11 to stamp `timestamp` in `Telemetry.record` (additive) | `test_budget_fold_from_ledger` + IMPLEMENTATION §6.3 |
| R6 | Provider shape differences leak through the normalization seam, coupling callers to a vendor | Med | High | refactor | one `LLMResponse` shape; shims are pure translation functions unit-tested without transport | `test_response_normalized_across_adapters`, `test_anthropic_gemini_translation_pure` |
| R7 | A call "succeeds" without its audit event (telemetry append fails silently) | Low | Med | reliability | the success path returns only after `Telemetry.record`; append failure propagates | `test_telemetry_llm_call_every_success` + IMPLEMENTATION §5 |
| R8 | The degrade extension re-tries an already-failed model or surprises with a paid model | Low | Med | correctness/cost | extension = catalog ∩ (tier free ∧ provider local) − tried, sorted by id | `test_exhaustion_degrades_to_local_free` |
| R9 | ~~`chain._catalog_ids` reads Config's internal model table (no frozen listing seam exists)~~ **RETIRED 2026-07-19 (feat/a2-accessors):** the degrade extension reads the additive `Config.models()` seam; `_catalog_ids` and the `config._models` reach are deleted; a static test (`test_degrade_uses_public_models_accessor`) keeps `router/` free of private Config reach | — | — | architectural-integrity | additive `Config.models()` (docs/43 §7) landed with A2's accessors branch | code (`chain.py`) + static test |

## Refactor-avoidance notes (priority #4)
- Freezing `LLMClient.call` + `LLMResponse` (IF-2 complete) lets S9/S10 build now; every
  provider/model change stays a config edit (docs/22 "models are data, not code").
- Adapters behind one `Adapter.complete` shape + an injectable `adapter_factory`: adding a
  provider is one adapter file + a registry line, no facade change.
- The transport seam (`FakeProvider` today, HTTP+`key_lookup` later) means the real
  network lands as a *new injected object*, not a rewrite — and tests never change.
- Reusing S7's `PIIRouteBlocked`/`Context` keeps one PII vocabulary across the seam
  (no parallel S8 refusal type to drift).

## Assumptions (must match partners' API.md)
- **S3 (merged):** `get_route/get_model/get_provider/budgets` per config/API.md; `Provider.kind`
  distinguishes `local` vs `cloud` (the PII-locality predicate keys on it).
- **S7 (merged):** `require_cloud_allowed(Context)` raises `PIIRouteBlocked` iff
  `contains_pii` — the frozen IF-3 guard; S8 calls it, never re-implements it.
- **S14 (merged):** `Telemetry.record` filters/redacts fields and appends `llm_call` via
  the real Ledger; failures surface.
- **S10/S12 (future):** supply `role` and (for critics) `critic_tier`; wire the real
  transport with `key_lookup` from A1's env seam at composition time.
