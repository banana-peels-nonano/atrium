# Capability Framework (S10) — TESTPLAN
Owner: A8 Framework Agent   (written BEFORE implementation)

Conventions per the merged suites: **live merged subsystems, no stubs** — real Config
over fixture dirs (`_a2_support`), real tmp-path Ledger, real Security, real Memory
(LanceDB on tmp_path + `FakeEmbedder`), real Router with A11 `FakeProvider` transports
(**no network anywhere** — INV-TEST-SAFE), typed fail-closed errors via `pytest.raises`,
INV mapping in docstrings, a seeded retry property vs an independent oracle. Support in
`tests/unit/_a8_support.py`.

## Unit tests (`tests/unit/test_framework.py`)
| Test | Asserts | Fake(s) | Covers |
|---|---|---|---|
| `test_run_happy_path_all_beats` | `run(state, venture)` returns `WorkflowResult` with: vault artifact written (redacted text), critique attached, `critic_tier` recorded, exactly ONE domain event (spec's `event_type`, `critic_tier` in payload), `event_id` real | full live stack + FakeProvider | 5-beat orchestration (docs/04 §5) |
| `test_prepare_deterministic_no_writes` | two `prepare` calls → equal frozen `CapInput` (doctrine + ≤k records from live S9); zero ledger events, zero vault files | live Memory | **INV-WF-1** (PREPARE side) + docs/04 §7 |
| `test_produce_receives_working_memory` | the messages actually sent to the transport contain the spec mission, the Doctrine text, and a seeded lesson's text (PREPARE feeds PRODUCE the PII-safe context) | recording transport | PREPARE→PRODUCE contract |
| `test_produce_idempotent` | same `CapInput` twice → identical frozen `Artifact` (same text/model); no files, no non-telemetry events | FakeProvider (canned) | **INV-WF-1** idempotency |
| `test_produce_retries_then_succeeds` | a transport failing exactly once → attempt 2 succeeds; result identical to the no-fault run; still zero state | FlakyTransport (support) | **INV-WF-1** retryable |
| `test_produce_exhausted_never_mutates_state` | ALL providers down → `BeatFailed("produce")` from `run`; **no vault file, ledger contains ONLY `llm_call`/`error` telemetry, registry replay unchanged** | FakeProvider (all error) | **INV-WF-1** (the founder-gate proof) |
| `test_retry_policy_property` (property, `seed` in `range(10)`) | seeded fail-k-then-succeed transports: `run` succeeds iff `k < spec.retries` (independent recomputation); on failure, the zero-mutation assert holds | FlakyTransport masks | **INV-WF-1** (property) |
| `test_checkpoint_only_mutating_beat` | driving the beats individually: after `prepare`+`produce_beat`+`critique_beat` → zero vault files, zero domain events; after `checkpoint` → exactly one of each | full live stack | **INV-WF-1** (beat isolation — the founder-gate proof) |
| `test_checkpoint_redacts_via_live_s7` | a canned artifact containing corpus PII → the vault file holds the REDACTED text (raw value absent), sidecar ref in the result; the domain event payload carries refs only | live Security, PII corpus | CHECKPOINT = live S7 (docs/04 §5) |
| `test_checkpoint_failure_leaves_no_partial_state` | a checkpoint-refusing Security probe (CheckpointError) → nothing written, nothing appended, error propagates; a failing-append Ledger probe → the just-written vault artifact is removed, error propagates | probe doubles (A7 R10 pattern) | **INV-WF-1** fail-closed |
| `test_critic_tier1_diff_family` | producer answers from family X, critic route lands family Y ≠ X → `Critique.tier == 1`, critic model recorded, family fn correct over the fixture catalog | FakeProvider | **INV-WF-2** |
| `test_critic_tier2_same_family_diff_model` | critic chain constrained to the producer's family (different model) → tier 2 recorded honestly | FakeProvider | **INV-WF-2** ladder |
| `test_critic_tier3_router_exhausted` | critic-role providers all down → tier 3: deterministic checklist critique (same artifact → byte-identical `Critique`), `model == "deterministic-checklist"`; `run` still completes | FakeProvider (critic down) | **INV-WF-2** floor |
| `test_critic_tier3_self_critique_refused` | the critic call answering with the SAME model that produced → tier 3 (never self-critique) | FakeProvider | **INV-WF-2** |
| `test_critique_never_fails_the_run` | with critic providers down, `run` returns a full `WorkflowResult` (tier 3) — critique exhaustion is degrade, not failure | FakeProvider | **INV-WF-2** always-available |
| `test_gate_needs_critic_take` | `WorkflowResult(critique=None, …)` → `NoCriticTake`; `checkpoint` without a critique refuses; every `run` result carries one | — | **INV-WF-3** |
| `test_registry_refuses_gate_red_event_types` (parametrized over `AUTHORIZATION_REQUIRED`) + `test_registry_refuses_unknown_event_type` | a `WorkflowSpec` naming a gate/RED event type → `AuthorityRefused` at registry construction; an unknown (non-catalog) event type → `AuthorityRefused` | — | no-authority MUST (docs/13) |
| `test_write_scope_enforced_via_memory_seam` | `Framework.write_lesson(spec, lesson)`: in-scope tags accepted (lesson lands in live S9); out-of-scope tags surface S9's `ScopeViolation`; nothing stored | live Memory | docs/54 §S11 (framework half) |
| `test_unknown_state_and_mismatch_refused` | no spec for state → `UnknownWorkflow`; `venture.state != state` → `StateMismatch`; both before any beat (zero events) | — | fail-closed preconditions |
| `test_spec_loader_parses_neutral_format` | a fixture `*.agent.md` → `CapabilitySpec` (mission/scope/inputs/outputs/READ/WRITE/escalation) | fixture specs | spec format (frozen) |
| `test_spec_loader_missing_section_refused` (parametrized over the 6 sections) + `test_spec_loader_missing_literal_refused` (parametrized over the 2 literals) + `test_spec_loader_empty_stub_refused` | each missing section / missing "no authority"/"stateless" literal → `SpecInvalid` naming it; the empty Phase-0 stub in `agents/` fails loudly | fixture specs + repo stub | spec format fail-closed |
| `test_opencode_generator_deterministic` | `generate_opencode(specs, out)` → one file per spec; run twice → byte-identical; frontmatter carries name+description; GENERATED-DO-NOT-EDIT stamp; regeneration overwrites cleanly | fixture specs | harness adapter |
| `test_framework_imports_no_authority` (static) | no module under `capabilities/` imports `charterhouse.governance` or `charterhouse.lifecycle` (docs/43 §5/§8) | — | no-authority structural |

## Integration tests (`tests/integration/test_framework_stack.py`)
| Test | Partner | Scenario | Expected |
|---|---|---|---|
| `test_it_full_stack_run_with_live_seams` | S3+S4+S7+S8+S9 all real | seeded lesson in live Memory → `run(FRAMED-flow)` for a real venture (ledger-built) with FakeProvider transports | artifact in the vault (redacted), ONE domain event with `critic_tier`, the seeded lesson's text present in the produced context, telemetry (`llm_call`) present for produce+critique |
| `test_it_gate_never_advances_itself` | S5 Lifecycle (live) + S4 | after a full `run`, the live Registry replay shows the venture's state UNCHANGED; then the test (playing S12/founder at GATE) calls the real `Lifecycle.transition` — only THAT moves state | the runner cannot advance a gate; the explicit live-S5 call can (docs/13, IF-4 composition) |

## Invariant coverage table
| INV / MUST | Test name | Tier |
|---|---|---|
| INV-WF-1 CHECKPOINT-only mutation; PRODUCE/CRITIQUE idempotent+retryable | `test_checkpoint_only_mutating_beat`, `test_produce_exhausted_never_mutates_state`, `test_produce_idempotent`, `test_produce_retries_then_succeeds`, `test_retry_policy_property`, `test_prepare_deterministic_no_writes`, `test_checkpoint_failure_leaves_no_partial_state` | unit |
| INV-WF-2 diff-family critic; ladder to tier-3; tier recorded | `test_critic_tier1_diff_family`, `test_critic_tier2_same_family_diff_model`, `test_critic_tier3_router_exhausted`, `test_critic_tier3_self_critique_refused`, `test_critique_never_fails_the_run` | unit |
| INV-WF-3 no gate without critic take | `test_gate_needs_critic_take`, happy-path assertions | unit |
| No-authority MUST (docs/13) | `test_registry_refuses_gate_red_event_types`, `test_framework_imports_no_authority` | unit + static |
| Scope enforcement (docs/54 §S11, framework half) | `test_write_scope_enforced_via_memory_seam` | unit |
| CHECKPOINT = live-S7 redact+scan (docs/04 §5) | `test_checkpoint_redacts_via_live_s7`, `test_it_full_stack_run_with_live_seams` | unit + integration |
| GATE is human / no self-advance (docs/13) | `test_it_gate_never_advances_itself` | integration |
| Neutral spec format + harness generator (docs/13 deliverables) | `test_spec_loader_parses_neutral_format`, `test_opencode_generator_deterministic` | unit |
| INV-DET (no env read; import DAG) | A1's static env-boundary test (sweeps `charterhouse/`) + `test_framework_imports_no_authority` | static |

## Fixtures/fakes needed (A11 shared harness + existing suites)
- **`FakeProvider`** (every transport; programmable errors) + a support-level
  `FlakyTransport` (fail-k-then-delegate) for retry tests and a recording transport for
  the context assertion.
- **Config fixture dirs** (`_a2_support.write_config`) with a catalog whose model ids
  span distinct families (llama/deepseek/gemini/claude) + a same-family-critic variant.
- **tmp-path real Ledger** (A3), **real Security** (S7), **real Memory** (A7's
  `_a7_support.make_memory` pattern: LanceDB tmp store + `FakeEmbedder`).
- **PII corpus** for the CHECKPOINT redaction test.
- Probe doubles (A7 R10 pattern): a `CheckpointError`-raising Security subclass and the
  `FailingAppendLedger`.

## Out of scope (test-safety, INV-TEST-SAFE)
No network socket anywhere (FakeProvider is every transport; LanceDB embedded; the
OpenCode generator writes local files and never invokes the harness or a model). No real
spend/send/deploy/charge — the framework structurally lacks those paths (that's the
point), and the registry test proves gate/RED event types are refused. The six REAL
capability contracts and their dry-runs are A9/S11's suite (Phase 5), not this one.
