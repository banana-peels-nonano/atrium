# Capability Framework (S10) — API
Owner: A8 Framework Agent   ·   Matches docs/40 §7 exactly (frozen seam)   ·   This doc freezes **IF-5 (Workflow runner)** (docs/43 §3, docs/52 §12) — unlocks A9 Content and A10 Conductor   ·   Built against live IF-1..IF-4 + the Memory surface (no stubs)

## Exposed surface

### `Workflow.run(state: State, venture: Venture, *, require=None, note="") -> WorkflowResult`
*(`require` is the additive docs/43 §7 kwarg, 2026-07-31: a per-run routing constraint that
overrides the row's own and applies to **both** LLM beats — the caller's way to say
`contains_pii`, which confines PRODUCE and CRITIQUE alike to local models, INV-PII-3.
`note` is the additive kwarg of 2026-08-01: the founder's own words about the idea, surfaced
in the prompt as its own `IDEA (founder's words):` section ahead of DOCTRINE. It arrives as
DATA — the caller reads it from the vault — so PREPARE keeps **no vault path** and beat
isolation stays structural. Already CHECKPOINTed at capture, so it carries redaction tokens,
never raw PII.)*
- **Preconditions:** `state` has a registered `WorkflowSpec` (the state→workflow table is
  DATA supplied at wiring — S12/A9 own the real table, docs/13); `venture.state == state`
  (a mismatch → `StateMismatch`, nothing runs).
- **Postconditions:** executes the four machine beats in order (docs/04 §5, docs/13):
  **PREPARE** (deterministic: `Memory.retrieve` → `CapInput`; zero writes) →
  **PRODUCE** (`Capability.produce` via `LLMClient.call(role, …)`; idempotent, retried up
  to `spec.retries`; zero state) → **CRITIQUE** (`Critic.critique` with the degrade
  ladder, INV-WF-2; zero state) → **CHECKPOINT** (deterministic and the ONLY mutating
  beat, INV-WF-1: live-S7 `Security.checkpoint` redact+scan fail-closed → write the clean
  artifact to the vault → append exactly ONE domain event (the spec's `event_type`, with
  `critic_tier` in the payload)). **GATE is human** — the runner never advances state
  (docs/13 "lets no gate advance itself"; Lifecycle remains the sole transition path).
  Returns `WorkflowResult{artifact_ref, sidecar_ref, critique, critic_tier, event_id,
  capability, model}` — constructible ONLY with a critic take attached (INV-WF-3).
- **Errors (fail closed):** `UnknownWorkflow` (no spec for state) / `StateMismatch` —
  before any beat; `BeatFailed("produce")` after `spec.retries` exhausted attempts —
  **with zero state mutated** (a model failure never corrupts state, INV-WF-1);
  S7 `CheckpointError` propagates — no vault write, no event, venture stays put;
  Ledger append failure propagates — the just-written vault artifact is removed (no
  artifact without its event). CRITIQUE never fails the run: its exhaustion degrades to
  the deterministic tier-3 checklist (always available, INV-WF-2).
- **Side effects:** ONE vault file + ONE domain event, both at CHECKPOINT only. (S8's
  `llm_call`/`error` telemetry appends during PRODUCE/CRITIQUE are observability, not
  venture state — see IMPLEMENTATION §6.5.) **Determinism:** PREPARE/CHECKPOINT
  deterministic; PRODUCE/CRITIQUE are the LLM path (behind the Router, docs/04 §7).
  **Auth class:** GREEN (drafts/briefs only; the spec registry refuses gate/RED event
  types — see `WorkflowRegistry`).

### `Capability.produce(input: CapInput) -> Artifact`
- One LLM call via the frozen `LLMClient.call(spec.role, messages, require=spec.require)`
  where `messages` are assembled deterministically from `CapInput` (the PREPARE output:
  neutral-spec mission/scope + Doctrine + top-K working memory + venture facts — the
  PII-safe context, docs/04 §7). Returns `Artifact{text, capability, role, model,
  venture_id, state}` (`model` = the answering model — the Critic's family input).
- **No authority, no durable state** (docs/40 §7): no writes, no events, no tokens;
  retryable by construction (same input → same call). Provider failures propagate
  (the runner owns the retry loop).

### `Critic.critique(artifact: Artifact) -> Critique`
- **The INV-WF-2 degrade ladder**, decided by what actually answers, recorded honestly:
  - **Tier 1** — `LLMClient.call("critic", …)` answers with a model whose **family
    differs** from `artifact.model`'s (family = the id's leading alphabetic token,
    IMPLEMENTATION §6.3).
  - **Tier 2** — the critic call answers same-family but a **different model** (the
    router had no cross-family candidate).
  - **Tier 3** — the critic call fails (`RouterError`) after `retries` attempts, OR
    answers with the **same model** that produced (self-critique refused) → the
    **deterministic checklist** critique (pure function over the artifact + spec's
    declared outputs; no LLM; always available).
  Returns `Critique{verdict, findings, tier, model, steer}`; `model` is the answering model
  or `"deterministic-checklist"`. Never raises for provider reasons — tier 3 is the floor.
- **Additive `require=` (docs/43 §7, 2026-07-31):** the run's routing constraint, passed to
  `LLMClient.call`. This carries the **INV-PII-3 obligation across the second LLM leg** — the
  artifact text is what gets critiqued, so a `contains_pii` run must confine the critic to
  local models too. (Before this seam, PRODUCE honoured the tag and CRITIQUE did not.)
- **Additive `steer` (docs/43 §7, 2026-07-31):** the critic's concrete
  what-to-build-instead / how-to-sharpen direction, split from `findings` on a literal
  `STEER:` label by a plain string partition. A critic that omits the label yields
  `steer == ""` and the whole answer as findings; **tier 3 never has a steer** (a
  deterministic checklist gives mechanical findings, not direction). Never synthesised —
  a blank steer is reported blank, so advice is always distinguishable from a floor.
- **Determinism:** tier 3 fully deterministic; tiers 1–2 are the LLM path.

### `WorkflowRegistry(specs: Mapping[State, WorkflowSpec])`  (wiring)
- Validates at construction (fail closed): every `event_type` is in the frozen docs/41
  catalog and **NOT** in `AUTHORIZATION_REQUIRED` — a workflow definition can never
  smuggle a gate/RED action through CHECKPOINT (`AuthorityRefused`; the no-authority
  MUST, docs/13). The registry is the runner's only state→workflow source.

### `load_capability_spec(path) -> CapabilitySpec` · `load_capability_specs(agents_dir)`
- Parses the **neutral** `agents/*.agent.md` contract format (docs/13: contracts, not
  prompts): required sections `Mission` / `Scope` / `Inputs` / `Outputs` /
  `Memory Scope` (READ:/WRITE: tag lists) / `Escalation`, plus the mandatory literals
  **"no authority"** and **"stateless"**. Any missing piece → `SpecInvalid` (fail
  closed). A8 froze the FORMAT; A9 filled the six real specs in Phase 5 (merged
  2026-07-19) — they are the live data this loader parses.
- `Memory Scope → WRITE` feeds S9's `write_lesson(..., scope=)` seam via
  `Framework.write_lesson(spec, lesson)` — an out-of-scope write surfaces S9's
  `ScopeViolation` unchanged (docs/54 §S11 enforcement, one refusal type).

### `generate_opencode(specs, out_dir) -> list[Path]`  (harness adapter)
- The **deterministic generator** (no LLM): neutral `CapabilitySpec`s → OpenCode
  agent-definition markdown (YAML frontmatter + contract body) under
  `adapters/harness/opencode/`. Byte-deterministic (same specs → same files), each file
  stamped GENERATED-DO-NOT-EDIT. Harness files are *derived*; the neutral specs stay the
  single source of truth (docs/13). claude-code/aider generators are later additive
  siblings (docs/30).

## Public value types
`WorkflowSpec{capability, role, k, retries, event_type, artifact_name, payload_fn,
require?}` · `CapabilitySpec{name, mission, scope, inputs, outputs, memory_read,
memory_write, escalation}` · `CapInput{spec, venture, state, working_set}` ·
`Artifact{text, capability, role, model, venture_id, state}` · `Critique{verdict,
findings, tier, model}` · `WorkflowResult{artifact_ref, sidecar_ref, critique,
critic_tier, event_id, capability, model}` · errors `FrameworkError` / `SpecInvalid` /
`UnknownWorkflow` / `StateMismatch` / `BeatFailed` / `NoCriticTake` /
`AuthorityRefused`; S9's `ScopeViolation` and S7's `CheckpointError` surface unchanged
(one refusal type per rule across seams — A6/A7 precedent).

## Consumed surface
- **Router (S8, IF-2, real):** `LLMClient.call(role, messages, tools?, require?)` —
  the ONLY model path (PRODUCE + CRITIQUE); `RouterError` drives retry/degrade.
- **Memory (S9, real):** `Memory.retrieve(task, k)` at PREPARE;
  `Memory.write_lesson(lesson, scope=)` for scoped capability writes.
- **Security (S7, IF-3, real):** `Security.checkpoint(text, doc_id)` at CHECKPOINT —
  fail-closed redact+scan; S10 re-implements NO S7 rule.
- **Ledger (S4, IF-1, real):** `Ledger.append(Event)` — the ONE domain event per run.
- **Lifecycle (S5, IF-4):** consumed as the **State/Venture vocabulary only**
  (`contracts/state.py`); the runner never calls `transition` (no gate advances itself —
  IMPLEMENTATION §6.2). S12 composes gate decisions with live S5.
- **A11 harness:** `FakeProvider` as every transport; `FakeEmbedder` behind Memory.

## Interface stability
- **Frozen (IF-5, this doc):** `Workflow.run(state, venture) -> WorkflowResult` +
  `Capability.produce(input) -> Artifact` + `Critic.critique(artifact) -> Critique` +
  the `CapInput`/`Artifact`/`Critique`/`WorkflowResult` shapes + INV-WF-1..3 semantics +
  the neutral `*.agent.md` section format. Breaking change = ICR (docs/43 §4).
- **Additive v1 notes (docs/43 §7):** `WorkflowSpec.require`; the optional
  `Critic.critique(artifact, spec=None)` second parameter (feeds the checklist's
  declared-outputs rules); extra `Critique.findings` detail; further harness
  generators (claude-code/aider) beside `generate_opencode`.
- **Internal/free to change:** beat method decomposition on `Workflow`
  (`prepare/produce_beat/critique_beat/checkpoint` — exposed for tests/S12 but not
  frozen), retry-loop internals, the `family_of` catalog-lookup wiring (since
  feat/a2-accessors the tier check reads the additive `Model.family` field; the
  canonical default derivation lives in `contracts.default_family`), checklist rule
  set, generator file layout, message-assembly template.
