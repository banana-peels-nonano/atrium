# 50 — ENGINEERING DECOMPOSITION
## Charter House as independent engineering subsystems
**Owner:** Program · **Source of truth:** Operating Model (`03`), all subsystem specs · **Status:** authoritative

---

## 0. Decomposition principle
Charter House is decomposed so that **the deterministic core is fully buildable and testable before any LLM is involved**, and so that subsystems with the fewest cross-dependencies can be built in parallel with minimal merge conflict. The seam boundaries follow the architecture's own seams (Operating Model): the *state machine over ventures*, the *model-provider seam*, and the *memory substrate*. We do not invent new seams; we harden the ones the architecture already defines.

## 1. The subsystems (workstreams)
Each subsystem is an independent workstream with one owning implementation agent (`51`), one code module boundary (`30`), and its own four contract docs (`56`).

| # | Subsystem | One-sentence charter | Depends on | LLM in path? |
|---|---|---|---|---|
| S1 | **Repository & Scaffolding** | The git repo, module skeleton, `.gitignore`, config-file stubs, folder tree | — | no |
| S2 | **Environment & Bootstrap** | Deterministic environment checks, path/K: discipline, `.env` loading, service healthchecks | S1 | no |
| S3 | **Configuration** | Typed loading + validation of `providers/models/routes/profiles`; precedence; reproducibility | S1 | no |
| S4 | **Ledger & Registry (Database)** | Append-only event store, venture registry, replay, integrity, backup | S1 | no |
| S5 | **State Machine / Lifecycle Engine** | Legal states, transitions, guards, WIP/slot limits, clocks (active-time) | S4 | no |
| S6 | **Governance Engine** | Action-class policy (GREEN/YELLOW/RED), authorization tokens, two-key, spend envelope, send budget | S4 | no |
| S7 | **Security & PII Pipeline** | Redaction at CHECKPOINT, deterministic PII/secret scanner, `contains_pii` routing block | S4, S3 | no |
| S8 | **Model Router & Adapters** | Role→model resolution, OpenAI-compatible + shim adapters, failover, budget guard | S3, S7 | calls LLMs |
| S9 | **Memory Engine** | Tiered memory, embeddings (local), LanceDB, top-K retrieval, consolidation/promotion | S4, S7, S8 | embeddings + LLM |
| S10 | **Capability Framework** | The 5-beat workflow runner + Critic ladder; neutral capability spec loader; harness (OpenCode) adapter | S5, S8, S9 | orchestrates LLMs |
| S11 | **Capabilities (content)** | The six capability contracts realized as neutral specs: Scout/Analyst/Builder/Growth/Librarian/Critic | S10 | LLMs |
| S12 | **Conductor (Orchestrator)** | The engine that binds S3–S11: runs workflows, enforces everything, produces Gate/Daily/Kill-Day Briefs & projections | S3–S11 | no (delegates) |
| S13 | **Projections & Briefs** | PIPELINE board, METRICS, Daily Brief, Gate Brief, Kill-Day Brief, Calibration report (all regenerable) | S4, S5, S6 | no |
| S14 | **Logging & Observability** | Structured logs, telemetry (tokens/$/latency per role/venture), audit trail | S1 | no |
| S15 | **Testing Harness** | Fixtures, golden set, lifecycle simulator, fakes for providers, invariant checkers | S1 | no |

> The **Conductor (S12)** is the integrator, not a monolith: it *delegates* to S5/S6/S7/S8/S9/S13 and holds no business logic those subsystems own. This keeps S12 thin and every rule enforced by exactly one subsystem.

## 2. Why this decomposition (design rationale, per priority order)
1. **Architectural integrity:** each subsystem owns exactly one architecture concern (state, governance, memory, routing…), so no invariant is enforced in two places.
2. **Ambiguity elimination:** the LLM/deterministic boundary is a subsystem boundary (S1–S7,S12–S15 deterministic; S8–S11 LLM), so "what must never be an LLM call" is structurally obvious.
3. **Parallelism:** S1→S4 unlock a wide fan-out (S5, S6, S7, S3, S14, S15 can proceed largely in parallel). See `52`.
4. **Minimal refactoring:** interfaces (`43`) are frozen at contract time; subsystems depend on interfaces, not implementations.
5. **Speed (lowest priority):** falls out of the above; we never trade a boundary for speed.

## 3. Subsystem boundaries (what each MUST NOT do)
- S5 (Lifecycle) MUST NOT know about models, memory content, or money — only states + guards.
- S6 (Governance) MUST NOT perform actions — only classify + authorize/deny.
- S7 (Security) MUST run deterministically — never an LLM in the redaction/scan path.
- S8 (Router) MUST NOT contain business rules about *which role* — it resolves role→model from config only; roles are assigned by S12/S10.
- S9 (Memory) MUST NOT route PII to cloud — it consumes S7's `contains_pii` tag and S8's local-only enforcement.
- S11 (Capabilities) MUST hold no authority and no durable state — produce artifact + recommendation, return.
- S12 (Conductor) MUST NOT re-implement any rule owned by S5/S6/S7 — it calls them.

## 4. Mapping to code modules
Full module tree in `30_repository.md`. One-line preview: `conductor/`, `lifecycle/`, `governance/`, `security/`, `router/` (+`router/adapters/`), `memory/`, `capabilities/` (+`capabilities/framework/`), `config/`, `ledger/`, `projections/`, `logging/`, `tests/`. Each maps 1:1 to a subsystem above.
