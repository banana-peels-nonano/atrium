# 51 — IMPLEMENTATION AGENTS
## The specialized agents Claude Code orchestrates (do not confuse with runtime Capabilities)
**Owner:** Program · **Source of truth:** `50` · **Status:** authoritative

> These are **build-time** agents (they write Charter House). They are distinct from the **runtime Capabilities** (Scout/Analyst/… inside the product). Claude Code acts as the orchestrator that dispatches these agents per the schedule in `70`. Each agent owns a disjoint set of files (`60`) and communicates only through frozen interfaces (`43`) and the ledger of PRs (`63`).

Each agent below is defined by: **Mission · Scope · Responsibilities · Deliverables · Inputs · Outputs · Dependencies · Files owned · APIs exposed · APIs consumed · Acceptance · Unit tests · Integration tests · Definition of Done (DoD).** Common DoD clauses (apply to all): four contract docs exist and are consistent (`56`); all owned files pass `61` standards; unit + integration tests green; no cross-owner file touched; merge gates in `63` pass.

---

## A0 — Scaffold Agent  (subsystem S1)
- **Mission:** stand up the repository skeleton so every other agent has a place to write.
- **Scope:** repo init, module tree, `.gitignore`, config stubs, empty contract docs. No logic.
- **Responsibilities:** create the module tree from `30`; add `.gitignore` (`.env`, caches, `*.private.md`, `Models/`, `Data/`, `Logs/`); seed `.env.example`; create empty `IMPLEMENTATION/API/TESTPLAN/RISKS` per subsystem.
- **Deliverables:** buildable empty repo; CI stub that runs the test harness.
- **Inputs:** `30`, `31`, `60`. **Outputs:** the repo.
- **Dependencies:** none (first).
- **Files owned:** repo root files, module `__init__` stubs, `.gitignore`, `.env.example`.
- **APIs exposed:** none. **APIs consumed:** none.
- **Acceptance:** `git status` clean; test harness runs (0 tests) green; tree matches `31` exactly.
- **Unit tests:** a structure test asserting the tree matches `31`. **Integration:** CI executes.
- **DoD:** every subsequent agent can create its files without touching another's.

## A1 — Environment Agent  (S2)
- **Mission:** guarantee the code runs only in a correctly-prepared environment.
- **Scope:** environment preflight, path resolution (K: discipline), `.env` loading, service healthchecks (Ollama, LanceDB path).
- **Responsibilities:** implement deterministic preflight that verifies env vars (`25`), K: paths exist and are writable, embedding endpoint reachable, C: headroom check; fail closed with actionable errors.
- **Deliverables:** `env/preflight`, path resolver, healthcheck.
- **Inputs:** `20`,`21`,`23`,`25`. **Outputs:** a validated runtime context object.
- **Dependencies:** A0.
- **Files owned:** `charterhouse/env/*`.
- **APIs exposed:** `EnvContext` (paths, profile, endpoints). **APIs consumed:** Config API (A2).
- **Acceptance:** preflight passes on a correctly set machine; each missing prerequisite yields one precise error.
- **Unit tests:** each failure mode → correct error. **Integration:** preflight → Config → healthcheck happy path.
- **DoD:** no other subsystem reads env vars directly; all go through `EnvContext`.

## A2 — Config Agent  (S3)
- **Mission:** make all configuration typed, validated, and reproducible; no hidden state.
- **Scope:** load/validate `providers.yaml`, `models.yaml`, `routes.yaml`, `profiles/*`, `.env`; precedence; schema.
- **Responsibilities:** schema-validate every config file (`25`); resolve the active profile; expose immutable typed config; reject unknown keys (fail closed).
- **Deliverables:** `config/` loader + schemas.
- **Inputs:** `25`,`22`. **Outputs:** typed `Config`.
- **Dependencies:** A0.
- **Files owned:** `charterhouse/config/*`, config schema files.
- **APIs exposed:** `Config` (get_route(role), get_model(id), get_provider(id), profile, budgets). **APIs consumed:** none.
- **Acceptance:** valid configs load; every malformed config fails with a located error; changing profile changes routes with zero code change.
- **Unit tests:** schema pass/fail matrix. **Integration:** Router (A6) resolves a role via Config.
- **DoD:** `INV-CFG` (no route names a model absent from `models.yaml`) enforced at load.

## A3 — Ledger/Registry Agent  (S4)  ·  also owns S9 memory-store parts jointly documented in `32`,`33`,`41`
- **Mission:** the append-only source of truth + venture registry with lossless replay.
- **Scope:** event append, read, replay-to-state; registry records; integrity (hash chain); backup snapshots.
- **Responsibilities:** implement the event catalog (`41`), append-only guarantees, deterministic replay to current state, corruption detection, snapshot/restore to `K:\Backups`.
- **Deliverables:** `ledger/`, `registry/`.
- **Inputs:** `32`,`41`,`12`. **Outputs:** ledger + registry APIs.
- **Dependencies:** A0.
- **Files owned:** `charterhouse/ledger/*`, `charterhouse/registry/*`.
- **APIs exposed:** `Ledger.append(event)`, `Ledger.read(filter)`, `Ledger.replay()`, `Registry.get/put/query`. **APIs consumed:** none.
- **Acceptance:** append is atomic + ordered; replay reconstructs identical state; tampering is detected.
- **Unit tests:** append/read/replay; hash-chain break detection; concurrent-append ordering. **Integration:** Lifecycle (A4) transition emits an event that replay reproduces.
- **DoD:** `INV-LEDGER` (state == replay(events)) holds under property-based tests.

## A4 — Lifecycle Agent  (S5)
- **Mission:** enforce the venture state machine and all slot/WIP/clock rules.
- **Scope:** states, legal transitions, guards, WIP (validating ≤3, SHAPING =1, building ≤1, HARVEST alumni ≤3), evidence TTL, active-time clocks, pivot=kill-and-fork, express-advance slot rule.
- **Responsibilities:** implement `42` exactly; expose `can_transition` + `transition`; own the shovel-ready overflow and OMW-ledger checks.
- **Deliverables:** `lifecycle/`.
- **Inputs:** `15`,`42`, Stress Test. **Outputs:** transition API + guard results.
- **Dependencies:** A3.
- **Files owned:** `charterhouse/lifecycle/*`.
- **APIs exposed:** `Lifecycle.can_transition(v, to)`, `Lifecycle.transition(v, to, token?)`. **APIs consumed:** Ledger, Registry.
- **Acceptance:** every illegal transition rejected; every WIP breach blocked; clocks measured in active-time from `experiment_live_at`.
- **Unit tests:** full transition matrix (legal/illegal); WIP/slot breach; TTL expiry; pivot fork lineage cap. **Integration:** three-venture Stress-Test simulation reproduces expected states (`55`).
- **DoD:** all `INV-SM-*` (`42`) verified; Stress-Test scenarios A/B/C pass.

## A5 — Governance Agent  (S6) + Security/PII (S7)
- **Mission:** ensure nothing crosses money/deploy/contact/PII boundaries without authorization; make PII exfiltration impossible.
- **Scope:** action-class table, tokens (single-use, two-key), spend envelope, send budget, redaction at CHECKPOINT, deterministic PII/secret scanner, `contains_pii` routing block.
- **Responsibilities:** implement `14`,`24`; classify actions; issue/verify/expire tokens; run redaction+scan; tag context; refuse cloud routes for PII.
- **Deliverables:** `governance/`, `security/`.
- **Inputs:** `14`,`24`, Stress Test (R-REDACT, R-ENVELOPE, R-CHARGE). **Outputs:** classify/authorize APIs + redaction pipeline.
- **Dependencies:** A3, A2.
- **Files owned:** `charterhouse/governance/*`, `charterhouse/security/*`.
- **APIs exposed:** `Gov.classify(action)`, `Gov.authorize(action, token)`, `Sec.redact(text)->(clean, sidecar)`, `Sec.scan(text)->findings`, `Sec.tag_pii(ctx)`. **APIs consumed:** Ledger, Config.
- **Acceptance:** every RED action without a valid token is refused; two-key requires token+passing check; a PII-tagged context is refused by every cloud adapter; scan is deterministic.
- **Unit tests:** class matrix; token single-use/expiry; envelope breach → re-RED; scanner precision on a PII corpus. **Integration:** memory write with PII → redacted store + local-only route (with A7/A8).
- **DoD:** all `INV-GOV-*` and `INV-PII-*` verified; no code path embeds/cloud-routes raw PII.

## A6 — Router Agent  (S8)
- **Mission:** make every model/provider swappable via config, with failover and budget guard.
- **Scope:** role→model resolution, OpenAI-compatible adapter + Anthropic/Gemini/Grok shims, failover chain, tier degradation, telemetry.
- **Responsibilities:** implement `11`,`22`; one `complete()` per adapter; normalize responses; honor `contains_pii` (local-only); record tokens/$/latency.
- **Deliverables:** `router/`, `router/adapters/*`.
- **Inputs:** `11`,`22`,`24`. **Outputs:** `LLMClient.call(role, messages, tools, require)`.
- **Dependencies:** A2, A5.
- **Files owned:** `charterhouse/router/*`.
- **APIs exposed:** `LLMClient.call(...)->LLMResponse`. **APIs consumed:** Config, Security (pii tag), Ledger (telemetry).
- **Acceptance:** switching profile reroutes with no code change; primary failure fails over silently; PII context never leaves local models; budget breach degrades tier.
- **Unit tests:** adapter request/response normalization (mocked HTTP); failover order; pii→local enforcement. **Integration:** live-optional smoke against one free provider + local embedding.
- **DoD:** `INV-ROUTE-*` verified; no business rule about *which role* lives here.

## A7 — Memory Agent  (S9)  ·  co-owns `32/33/41` with A3
- **Mission:** the compounding knowledge substrate that improves with age.
- **Scope:** embeddings (local, frozen model), LanceDB schema, top-K retrieval (semantic+tag+recency+confidence), consolidation/promotion/retirement, index rebuild.
- **Responsibilities:** implement `12`,`33`; assemble working memory (Doctrine + top-K); never dump full stores; run consolidation as reversible views over the immutable ledger.
- **Deliverables:** `memory/`.
- **Inputs:** `12`,`33`,`41`. **Outputs:** retrieval + consolidation APIs.
- **Dependencies:** A3, A5(sec), A6(embeddings via router or direct Ollama).
- **Files owned:** `charterhouse/memory/*`.
- **APIs exposed:** `Memory.retrieve(task)->WorkingSet`, `Memory.write_lesson(...)`, `Memory.consolidate()`, `Memory.reindex()`. **APIs consumed:** Ledger, Security, Router/Embeddings.
- **Acceptance:** retrieval returns top-K only; PII never embedded; consolidation never edits the ledger; re-index reproduces retrievable state.
- **Unit tests:** ranking weights; retired/superseded exclusion; embed→store→retrieve round trip; re-index determinism. **Integration:** kill→salvage→lesson→retrieval available at next gate.
- **DoD:** `INV-MEM-*` verified; embedding model id pinned; changing it is a guarded re-index.

## A8 — Capability-Framework Agent  (S10)
- **Mission:** the 5-beat workflow runner + Critic ladder + neutral-spec loader + harness adapter.
- **Scope:** PREPARE·PRODUCE·CRITIQUE·CHECKPOINT·GATE runner; retry/escalation; Critic tier ladder; load `agents/*.agent.md`; OpenCode adapter generation.
- **Responsibilities:** implement `13`(framework part); idempotent PRODUCE; cross-family CRITIQUE with degrade ladder; CHECKPOINT calls Security+Ledger; never advance a gate itself.
- **Deliverables:** `capabilities/framework/*`, `adapters/harness/opencode/*`.
- **Inputs:** `13`, Capability Contracts, `43`. **Outputs:** `run_workflow(state, venture)`.
- **Dependencies:** A4, A6, A7, A5.
- **Files owned:** `charterhouse/capabilities/framework/*`, `adapters/harness/*`.
- **APIs exposed:** `Workflow.run(state, venture)->Result`. **APIs consumed:** Lifecycle, Router, Memory, Security, Ledger.
- **Acceptance:** a model failure at PRODUCE/CRITIQUE causes retry, not state change; CRITIQUE tier recorded; CHECKPOINT is the only mutating beat.
- **Unit tests:** beat isolation; retry/escalation; critic degrade ladder to tier-3. **Integration:** dry-run one state end-to-end with a fake model.
- **DoD:** `INV-WF-*` verified; no gate advances without a Critic take attached.

## A9 — Capability-Content Agent  (S11)
- **Mission:** realize the six capability contracts as neutral specs (not prompts-as-code).
- **Scope:** Scout, Analyst, Builder, Growth, Librarian neutral specs + Critic mode spec, each honoring its contract (`13`, Capability Contracts).
- **Responsibilities:** encode mission/scope/inputs/outputs/memory-scope/escalation per contract; wire design-partner recruitment (Growth), two-sub-gate evidence (Analyst), salvage types (Librarian).
- **Deliverables:** `agents/*.agent.md` (neutral, harness-generated downstream).
- **Inputs:** Capability Contracts, `13`. **Outputs:** the neutral specs.
- **Dependencies:** A8.
- **Files owned:** `agents/*.agent.md`.
- **APIs exposed:** none (data). **APIs consumed:** framework loader.
- **Acceptance:** each spec's declared memory scope matches `13`; no capability holds authority.
- **Unit tests:** spec schema validation; scope-vs-contract check. **Integration:** each capability runs its beat in a dry-run venture.
- **DoD:** all six contracts satisfied; scope enforcement testable by the framework.

## A10 — Conductor Agent  (S12) + Projections (S13)
- **Mission:** the thin integrator that binds everything and produces the human-facing briefs.
- **Scope:** command surface (`10`), workflow dispatch, guard/authorization enforcement via S4–S9, Gate/Daily/Kill-Day Brief + PIPELINE/METRICS/Calibration projections.
- **Responsibilities:** implement `10`; hold NO rule owned by S5/S6/S7 (call them); assemble the fixed-schema Gate Brief (must include Critic tier).
- **Deliverables:** `conductor/`, `projections/`.
- **Inputs:** `10`,`13`,`40`. **Outputs:** CLI/command API + projections.
- **Dependencies:** A2–A9.
- **Files owned:** `charterhouse/conductor/*`, `charterhouse/projections/*`.
- **APIs exposed:** the command surface (`40`). **APIs consumed:** all subsystem APIs.
- **Acceptance:** every command enforces its guards via the owning subsystem; no Gate Brief lacks a Critic section; crash→replay loses nothing.
- **Unit tests:** each command's guard path; brief schema. **Integration:** full venture dry-run Capture→Graduate (no real spend/send/deploy).
- **DoD:** `INV-COND-*` verified; Conductor holds no duplicated rule.

## A11 — Test Agent  (S15) + Logging (S14) — cross-cutting, active from Phase 0
- **Mission:** ensure nothing is implemented without a validation path; provide fakes, fixtures, simulators, invariant checkers, structured logging + telemetry.
- **Scope:** all test tiers (`55`), provider fakes, golden set, lifecycle simulator, invariant harness; structured logs + per-role token/$/latency telemetry.
- **Responsibilities:** own the test harness and shared fakes; every other agent writes tests *into* this harness; own `logging/`.
- **Deliverables:** `tests/`, `charterhouse/logging/*`.
- **Inputs:** `55`, all acceptance criteria (`54`). **Outputs:** runnable test suites + logging API.
- **Dependencies:** A0.
- **Files owned:** `tests/*` (shared fixtures/fakes/simulator), `charterhouse/logging/*`.
- **APIs exposed:** `Log`, test fixtures/fakes. **APIs consumed:** all (as test doubles).
- **Acceptance:** every subsystem has runnable unit+integration tests; the lifecycle simulator reproduces Stress-Test A/B/C; CI blocks on red.
- **Unit tests:** the harness self-tests. **Integration:** the simulator.
- **DoD:** `55` fully realized; no merge passes with red tests.

---

## Ownership summary (disjoint file domains)
A0 root/scaffold · A1 `env/` · A2 `config/` · A3 `ledger/`,`registry/` · A4 `lifecycle/` · A5 `governance/`,`security/` · A6 `router/` · A7 `memory/` · A8 `capabilities/framework/`,`adapters/harness/` · A9 `agents/` · A10 `conductor/`,`projections/` · A11 `tests/`,`logging/`. No file has two owners (`60`).
