# Capability Framework (S10) — IMPLEMENTATION
Owner: A8 Framework Agent   Subsystem: S10   Source of truth: docs/13 (build contract, frozen beats) + docs/04 §5–§7 + docs/40 §7 (seam) + docs/43 (IF-5) + docs/54 §S10 / docs/55

## 1. Responsibility (one paragraph)
S10 owns the 5-beat workflow runner (PREPARE → PRODUCE → CRITIQUE → CHECKPOINT → GATE),
the Critic degrade ladder, the neutral capability-spec loader, and the OpenCode harness
generator. It orchestrates capabilities but MUST NOT: grant any authority (no
send/spend/deploy/token path exists here — the spec registry even refuses gate/RED event
types), advance any gate or call `Lifecycle.transition` (GATE is human; S12 composes),
redact (S7 owns it — CHECKPOINT *calls* the live `Security.checkpoint`), decide routing
(role → model is S8+S3's), write memory outside a capability's declared scope (S9's
`scope` seam enforces), or hold durable state of its own (vault artifacts + ledger
events are the system's, written only at CHECKPOINT).

## 2. Invariants enforced
- **INV-WF-1** — "CHECKPOINT is the only state-mutating beat; PRODUCE/CRITIQUE are
  idempotent + retryable." Guaranteed structurally in `runner.py`: `prepare` builds a
  frozen `CapInput` (read-only `Memory.retrieve`); `produce_beat`/`critique_beat` call
  the Router and return frozen values — no vault path, no `Ledger.append`, no store
  handle is even reachable from `Capability`/`Critic`; only `checkpoint` touches the
  vault + ledger, and its failure modes (S7 `CheckpointError`, append failure) leave
  zero partial state (write-then-append with artifact rollback). A `BeatFailed` produce
  after `spec.retries` attempts mutates nothing.
- **INV-WF-2** — "CRITIQUE on a different model family; ladder to deterministic tier-3
  always available; tier recorded." Guaranteed in `critic.py`: the ladder is decided by
  what actually answered (family ≠ → tier 1; same family, different model → tier 2;
  router exhausted OR same-model answer → tier 3 checklist, a pure function). The tier
  is recorded in `Critique.tier`, `WorkflowResult.critic_tier`, and the CHECKPOINT
  event payload.
- **INV-WF-3** — "no gate presentable without an attached Critic take." Guaranteed by
  construction: `WorkflowResult.__post_init__` refuses `critique=None`
  (`NoCriticTake`); `checkpoint` requires the `Critique` argument; tier 3's
  availability means a critique always exists.

## 3. Internal design
Modules under `charterhouse/capabilities/framework/` (deterministic except the two
Router-mediated beats; **the only LLM path in S10 is `LLMClient.call`**):
- `types.py` — frozen dataclasses (`WorkflowSpec`, `CapabilitySpec`, `CapInput`,
  `Artifact`, `Critique`, `WorkflowResult`) + error taxonomy. `WorkflowResult` enforces
  INV-WF-3 in `__post_init__`.
- `spec_loader.py` — the neutral `*.agent.md` parser (section headings → fields;
  READ:/WRITE: tag lists; mandatory "no authority"/"stateless" literals). Fail closed
  (`SpecInvalid` names the missing piece).
- `capability.py` — `Capability.produce`: deterministic message assembly (spec mission/
  scope + doctrine + top-K lesson texts + venture facts) → one `LLMClient.call`.
- `critic.py` — `Critic.critique`: critic-role call + family comparison + the tier-3
  checklist (`_checklist`: non-empty text, no dangling TODO/FIXME/XXX markers, every
  spec-declared output named in the artifact, length sanity) — pure, ordered findings.
- `registry.py` — `WorkflowRegistry`: state→`WorkflowSpec` table validation
  (catalog membership; `AUTHORIZATION_REQUIRED` exclusion → `AuthorityRefused`).
- `runner.py` — `Workflow`: the beat methods + `run` orchestration + the retry loop
  (`spec.retries` total attempts per LLM beat) + `write_lesson(spec, lesson)`
  (S9 `scope=` pass-through).
- `harness_opencode.py` — `generate_opencode`: spec → YAML-frontmatter markdown,
  byte-deterministic, GENERATED-DO-NOT-EDIT stamped. The thin CLI entry lives at
  `adapters/harness/opencode/generate.py` (docs/31 layout); generated agent files land
  beside it. Logic stays importable/tested inside the package.
**Durable state: none owned.** Vault artifacts belong to the venture (S12/S7 rules);
events to the ledger; specs to A9's `agents/`.

## 4. Dependencies
- **S8 Router (IF-2, real):** `LLMClient.call(role, messages, tools?, require?) ->
  LLMResponse{text, model, …}`; `RouterError`/`ProvidersExhausted` drive retry/degrade.
- **S9 Memory (real):** `Memory.retrieve(TaskContext, k) -> WorkingSet`;
  `Memory.write_lesson(Lesson, scope=) -> lesson_id` (+ `ScopeViolation`).
- **S7 Security (IF-3, real):** `Security.checkpoint(text, doc_id) ->
  CheckpointResult{clean, sidecar_ref, contains_pii}`; `CheckpointError` fail-closed.
- **S4 Ledger (IF-1, real):** `Ledger.append(Event) -> event_id`; `EventType` +
  `AUTHORIZATION_REQUIRED` from `charterhouse.contracts.events`.
- **S5 Lifecycle (IF-4):** vocabulary only — `State`/`Venture` from
  `charterhouse.contracts.state`. No runtime call (§6.2).
- **A11 harness:** `FakeProvider` (every transport), `FakeEmbedder`, corpus fixtures.

## 5. Failure behavior
Every failure fails closed, typed, with zero partial state:
- No spec for the state → `UnknownWorkflow`; `venture.state != state` → `StateMismatch`
  — both before any beat runs.
- PRODUCE: each router failure retried up to `spec.retries` total attempts; exhausted →
  `BeatFailed("produce", …)` — no vault file, no domain event, registry replay
  unchanged (INV-WF-1's teeth).
- CRITIQUE: router exhaustion is NOT a failure — deterministic tier-3 floor (INV-WF-2).
- CHECKPOINT: S7 `CheckpointError` (residual PII) propagates → nothing written/appended;
  a ledger-append failure removes the just-written vault artifact (no artifact without
  its event) and propagates.
- Registry construction: unknown/gate/RED event type → `AuthorityRefused` at wiring,
  before anything can run.
- Spec parsing: any missing section/literal → `SpecInvalid` naming it.
No "guess/continue" path; the runner never returns a partial `WorkflowResult`.

## 6. Open questions → RESOLVED
1. **Where does the state→capability table live?** docs/13 gives the six capabilities;
   docs/42 the states — but no doc fixes the mapping as S10's. RESOLVED: the table is
   DATA (`WorkflowRegistry`) supplied at wiring; S12/A9 own the real rows (Conductor
   commands know their states). S10 freezes the row *shape* (`WorkflowSpec`) and the
   no-authority validation. Tests use fixture rows.
2. **"Consumes Lifecycle (S5)" — how, without advancing gates?** RESOLVED: as the
   State/Venture *vocabulary* (contracts module) + the `venture.state == state` guard.
   The runner never calls `can_transition/transition` — docs/13 "lets no gate advance
   itself" and docs/43 §5 ("Capabilities import nothing that grants authority") outrank
   the dependency edge, which docs/50 shows for build ordering (IF-4 before IF-5). The
   anti-coupling test pins it: `capabilities/` imports neither `lifecycle/` nor
   `governance/`.
3. **Model "family" derivation.** No `family` field exists on the frozen `Model` shape.
   RESOLVED: family = the model id's leading alphabetic token, lowercased
   (`claude-sonnet`→`claude`, `gemini-2.0-flash`→`gemini`, `llama3.1-8b-local`→`llama`,
   `deepseek-chat-free`→`deepseek`) — deterministic over the committed catalog.
   Cross-note to A2: an additive `Model.family` field would harden this (router-R9
   pattern); the derivation is isolated in one function pending it.
4. **When is the critic tier knowable?** Only AFTER the critique call returns (tier 1
   vs 2 depends on which model answered). RESOLVED: the tier is recorded in
   `Critique.tier` + `WorkflowResult.critic_tier` + the CHECKPOINT event payload. The
   router's additive `critic_tier` kwarg (A6) remains for S12's `gate_decision`
   telemetry; S10 does not pretend to know the tier pre-call.
5. **Are S8's telemetry appends a CHECKPOINT-only violation?** During PRODUCE/CRITIQUE
   the Router appends `llm_call`/`error` events (INV-ROUTE-4 — S8's invariant, not
   ours). RESOLVED: INV-WF-1's "state" = vault artifacts + non-telemetry domain events +
   the registry projection (none of which telemetry touches — `llm_call`/`error` carry
   no venture state transition). Tests assert exactly this taxonomy: after a failed
   PRODUCE, the ledger contains ONLY `llm_call`/`error` events and the registry replay
   is unchanged.
6. **The `agents/*.agent.md` files are empty A9 stubs — what does A8 ship?** RESOLVED:
   A8 freezes the neutral FORMAT (parser + required sections + the no-authority/
   stateless literals) and tests it with fixture specs; the six real contracts are A9's
   Phase-5 deliverable (docs/51). The loader is strict per file; it never invents
   content for an empty stub (`SpecInvalid`).
7. **What exactly does the OpenCode adapter do — call OpenCode?** RESOLVED: it is a
   deterministic *generator* (docs/30 "generators"; docs/51 "OpenCode adapter
   generation"): neutral spec → OpenCode agent markdown (frontmatter + body). It never
   invokes the harness, never calls a model, and its output is derived/regenerable —
   the neutral specs remain the single source of truth (the FORGE harness-neutrality
   principle). Runtime harness invocation is a later, separate concern (S12 era).
