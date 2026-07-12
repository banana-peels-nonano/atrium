# Router (S8) — TESTPLAN
Owner: A6 Router Agent   (written BEFORE implementation)

Conventions per the merged suites: real Config over fixture config dirs (`_a2_support`),
real tmp-path Ledger, A11's `FakeProvider` as the injected transport (**no network
anywhere** — INV-TEST-SAFE), typed fail-closed errors via `pytest.raises`, INV mapping in
docstrings, a seeded failure-mask property test. Support in `tests/unit/_a6_support.py`.

## Unit tests (`tests/unit/test_router.py`)
| Test | Asserts | Fake(s) | Covers |
|---|---|---|---|
| `test_role_resolved_from_config_only` | the same `call("reasoning", …)` under two profiles resolves different models with zero S8 code change; the chosen model is exactly the profile's route primary | real Config (two-profile fixture), FakeProvider | **INV-ROUTE-1** (docs/54 §S8 row 1) |
| `test_unknown_role_propagates_config_error` | `call("no-such-role", …)` raises Config's `UnknownRole` — S8 adds no default/fallback role logic | real Config | **INV-ROUTE-1** fail-closed |
| `test_failover_primary_down_uses_first_fallback` | primary transport programmed to fail → the first fallback answers; the response names the fallback model; attempt order == config order | FakeProvider (error) | **INV-ROUTE-2** |
| `test_failover_order_deterministic_property` (property, `seed` in `range(20)`) | for seeded random failure masks over the chain, the answering model == the first healthy candidate in `[primary, *fallback]` order (independent recomputation) | FakeProvider masks | **INV-ROUTE-2** (property) |
| `test_exhaustion_degrades_to_local_free` | all configured candidates fail → the free/local degrade extension (catalog, sorted, minus tried) answers | FakeProvider | **INV-ROUTE-2** degrade |
| `test_exhaustion_signals_pause` | configured chain AND degrade extension all fail → `ProvidersExhausted` + an `error` event appended; no partial response | FakeProvider (all down) | **INV-ROUTE-2** pause signal |
| `test_pii_chain_excludes_cloud` | `require.contains_pii=True` with a cloud primary + local fallback → the local model answers; the cloud transport was **never called**; a `pii_block` event names the excluded route | FakeProvider spies | **INV-ROUTE-3 / INV-PII-3** |
| `test_pii_no_local_candidate_blocked` | PII tag over an all-cloud config (no local model in catalog) → `PIIRouteBlocked`; **zero transport calls**; `pii_block` appended | FakeProvider spies | **INV-ROUTE-3** fail-closed |
| `test_cloud_adapter_hard_guard` | calling a **cloud adapter directly** with a `contains_pii` `Context` raises `PIIRouteBlocked` from the merged S7 guard before any transport call — the defense-in-depth layer independent of the chain filter | FakeProvider spy | **INV-PII-3** (adapter boundary) |
| `test_local_adapter_accepts_pii` | the local (Ollama-kind) adapter completes a `contains_pii` context — local execution is the PII-legal path | FakeProvider | INV-ROUTE-3 complement |
| `test_budget_80pct_drops_paid_tier` | with `spent_usd` ≥ 80% of `budgets.monthly_usd`, a paid primary is skipped and the free fallback answers (docs/14 auto-degrade); under 80% the paid primary is used | real Config (cheap-cloud fixture), injected spend | budget guard |
| `test_budget_fold_from_ledger` | the default spend fold sums `llm_call.cost_usd` events from the ledger (un-timestamped events count — conservative) | real Ledger + seeded events | budget fold |
| `test_telemetry_llm_call_every_success` | every successful `call` appends exactly one `llm_call` event with `{role, model, provider, tokens, cost_usd, latency_ms}`; `cost_usd` == tokens × catalog prices; `critic_tier` stamped when supplied | real Ledger | **INV-ROUTE-4** |
| `test_min_ctx_and_capability_filters` | `require.min_ctx` drops small-ctx candidates; `needs_tools`/`needs_web` drop models lacking the capability in `good_at`; an emptied chain → `NoEligibleModel` naming the constraint | real Config | require merging |
| `test_response_normalized_across_adapters` | the same transport result through OpenAI-compat, Anthropic shim, and Gemini shim yields byte-identical `LLMResponse` shapes (provider differences never leak) | FakeProvider | adapter normalization |
| `test_anthropic_gemini_translation_pure` | the shims' `to_provider_request`/`from_provider_response` translation functions round-trip OpenAI-shaped messages (system handling, role names) — pure, no transport | none | shim correctness |

## Integration tests (`tests/integration/test_router_stack.py`)
| Test | Partner | Scenario | Expected |
|---|---|---|---|
| `test_it_pii_flow_tag_to_local_route` | S7 (real `Sec.tag`) + S3 (real Config) + S4 (real Ledger) | a context containing corpus PII is tagged by the real scanner → `call` with the tagged flag | routed to the local model; cloud transports untouched; `pii_block` + `llm_call` events on the ledger |
| `test_it_committed_config_free_profile_routes` | the real committed `config/` | `call("reasoning")` under the `free` profile with FakeProvider transports | resolves the committed free-tier primary; telemetry recorded |

## Invariant coverage table
| INV / MUST | Test name | Tier |
|---|---|---|
| INV-ROUTE-1 role→model from Config only | `test_role_resolved_from_config_only`, `test_unknown_role_propagates_config_error` | unit |
| INV-ROUTE-2 deterministic failover → degrade → pause | `test_failover_primary_down_uses_first_fallback`, property, `test_exhaustion_degrades_to_local_free`, `test_exhaustion_signals_pause` | unit |
| INV-ROUTE-3 / INV-PII-3 (S8 half) | `test_pii_chain_excludes_cloud`, `test_pii_no_local_candidate_blocked`, `test_cloud_adapter_hard_guard`, `test_local_adapter_accepts_pii`, `test_it_pii_flow_tag_to_local_route` | unit + integration |
| INV-ROUTE-4 telemetry | `test_telemetry_llm_call_every_success`, `test_budget_fold_from_ledger` | unit |
| Budget degrade (docs/14) | `test_budget_80pct_drops_paid_tier` | unit |
| Profile switch zero-code (docs/54 §S8) | `test_role_resolved_from_config_only`, `test_it_committed_config_free_profile_routes` | unit + integration |
| Normalization (docs/11 "never leak") | `test_response_normalized_across_adapters`, `test_anthropic_gemini_translation_pure` | unit |
| `INV-DET` (no env read; import DAG) | A1's static env-boundary test (already green over `charterhouse/`) + anti-coupling check | static |

## Fixtures/fakes needed (A11 shared harness + existing suites)
- **`FakeProvider`** (`tests.fakes`) — the injected transport everywhere; programmable
  errors/rate-limits drive failover. **No real network in any test.**
- **Config fixture dirs** (`_a2_support.write_config`) with router-shaped catalogs (paid +
  free + local models); the committed `config/` for the integration test.
- **tmp-path real Ledger** (A3 convention) for telemetry/pii_block/error assertions.
- **PII corpus** (`tests.fixtures.pii_corpus`) + real S7 `Sec.tag` for the integration flow.

## Out of scope (test-safety, INV-TEST-SAFE)
No real provider call, no network socket, no API key anywhere: adapters only ever see the
injected `FakeProvider` transport. The real HTTP transport (with its `key_lookup` seam) is
deliberately NOT part of A6 (IMPLEMENTATION §6.1); live smoke is optional and non-gating.
