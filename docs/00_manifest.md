# 00 — MANIFEST
## Charter House Implementation Bible · index, ownership map, and reading order
**Owner:** Program · **Status:** authoritative · **Version:** IB-1.0 · **Architecture baseline:** Charter House v1.1 (frozen)

---

## 0. What this repository is
This is the **Implementation Bible (IB)** — the engineering specification between the frozen Charter House architecture and the code Claude Code will write. The architecture is **immutable** (§4). This repo does not redesign it; it *translates* it into unambiguous, buildable, testable contracts.

**Success test:** Claude Code, reading this repo, should never ask *"what should I build?"* — only *"how do I implement this specification?"* Any document that leaves the first question open is defective and must be fixed before implementation of the affected subsystem begins.

## 1. Frozen architecture baseline (inputs — do not modify)
Vision · Doctrine · Operating Model · Founder Operating Manual · Conductor Specification · Capability Contracts · Governance Architecture · Memory Architecture · Repository Architecture · Lifecycle · Stress Test · Revision Register (v1.1) · Environment Specification. Every IB document cites its source under **Source of truth**.

## 2. Repository map (every document, its single responsibility, its owner)
| Doc | Responsibility (single) | Owner agent | Derives from |
|---|---|---|---|
| `00_manifest.md` | Index, ownership, reading order, doc dependency graph | Program | all |
| `README.md` | Entry point + how Claude Code consumes this repo | Program | 00, 70 |
| `01_vision.md` | Why Charter House exists (implementation-invariant framing) | Program | Vision |
| `02_doctrine.md` | Non-negotiable rules as machine-checkable invariants | Program | Doctrine |
| `03_architecture.md` | The five primitives + two seams as build targets | Program | Operating Model |
| `04_operating_model.md` | How the primitives interact at runtime | Program | Operating Model |
| `05_founder_manual.md` | Human-in-the-loop touchpoints the software must expose | Program | Founder Manual |
| `10_conductor.md` | Conductor engine build contract | Conductor Agent | Conductor Spec |
| `11_router.md` | Model/provider router + adapters build contract | Router Agent | Env Spec, Memory Arch |
| `12_memory.md` | Tiered memory + retrieval + consolidation build contract | Memory Agent | Memory Arch |
| `13_capabilities.md` | Capability framework + six capability contracts | Capability Agent | Capability Contracts |
| `14_governance.md` | Action-class engine, tokens, PII routing build contract | Governance Agent | Governance Arch |
| `15_lifecycle.md` | State machine + transition guards build contract | Lifecycle Agent | Lifecycle, Stress Test |
| `20_environment.md` | Runtime environment assumptions for code | Environment Agent | Env Spec |
| `21_installation.md` | Deterministic setup the code depends on | Environment Agent | Env Spec |
| `22_models.md` | Model role catalog + routing profiles as data | Router Agent | Env Spec |
| `23_storage.md` | On-disk layout, paths, K: discipline for code | Environment Agent | Env Spec, Repo Arch |
| `24_security.md` | Secrets, PII, redaction, scan — engineering rules | Governance Agent | Governance, Memory |
| `25_configuration.md` | Config schemas + precedence + reproducibility | Config Agent | Env Spec |
| `30_repository.md` | Code repository layout + module boundaries | Program | Repo Arch |
| `31_folder_structure.md` | Exact directory tree the code creates/uses | Environment Agent | Repo Arch |
| `32_database.md` | Ledger + registry schema, integrity, replay | Memory Agent | Memory Arch |
| `33_vector_memory.md` | LanceDB schema, embedding contract, re-index rules | Memory Agent | Memory Arch |
| `40_api_contracts.md` | Every internal API surface, typed | Interface Agent | Conductor/Router/Memory |
| `41_events.md` | Ledger event catalog (canonical, versioned) | Memory Agent | Memory Arch |
| `42_state_machine.md` | States, transitions, guards, invariants (formal) | Lifecycle Agent | Lifecycle |
| `43_interfaces.md` | Cross-subsystem interface boundaries + versioning | Interface Agent | all subsystems |
| `50_engineering_decomposition.md` | Subsystems as independent workstreams | Program | 03 |
| `51_implementation_agents.md` | The specialized implementation agent roster | Program | 50 |
| `52_dependency_graph.md` | Build dependency DAG, parallelism, critical path | Program | 50, 51 |
| `53_build_phases.md` | Phases 0–9: objectives, outputs, exit criteria | Program | 52 |
| `54_acceptance_criteria.md` | Per-subsystem acceptance + Definition of Done | Program | all subsystems |
| `55_testing_strategy.md` | All test tiers, defined before implementation | Test Agent | all |
| `56_contract_templates.md` | IMPLEMENTATION/API/TESTPLAN/RISKS templates | Program | all |
| `60_repository_rules.md` | Repository hygiene + ownership enforcement | Program | 30 |
| `61_coding_standards.md` | Language, style, error handling, determinism rules | Program | Env Spec |
| `62_documentation_rules.md` | How code docs + IB docs stay in sync | Program | all |
| `63_git_and_merge_strategy.md` | Branching, PR gates, merge invariants | Program | all |
| `70_claude_code_execution_plan.md` | Exactly how Claude Code consumes + executes this repo | Program | all |

## 3. Reading order (Claude Code, first pass)
1. `README` → `00_manifest` → `70_execution_plan` — the process.
2. `02_doctrine`, `03_architecture`, `42_state_machine`, `14_governance`, `24_security` — the invariants that must never break.
3. `50_decomposition` → `52_dependency_graph` → `53_build_phases` — what to build, in what order.
4. `56_contract_templates` — the four docs each subsystem produces *before* coding.
5. Per active phase: the subsystem doc (`10`–`15`, `20`–`33`) + `40`–`43` + `54`/`55`.

## 4. Immutability rule (hard)
The architecture is frozen. An agent may raise a **Blocking Impossibility** (see `70`) *only* when a spec is physically un-implementable — not merely inconvenient, slower, or less elegant. A Blocking Impossibility halts the affected workstream and escalates to Program; it never authorizes silent architecture change. Everything else is implemented as written.

## 5. Document dependency graph
```
README ─► 00_manifest ─► 70_execution_plan
00 ─► 02_doctrine ─► 03_architecture ─► 04_operating_model ─► 05_founder_manual
03 ─► 50_decomposition ─► 51_agents ─► 52_dependency_graph ─► 53_build_phases
15_lifecycle ─► 42_state_machine            (the spine)
12_memory ─► 32_database, 33_vector_memory, 41_events
14_governance ─► 24_security                (PII/secrets)
{10..15} ─► 40_api_contracts ─► 43_interfaces
all subsystems ─► 54_acceptance ─► 55_testing
30 ─► 60_repo_rules ─► 61_coding ─► 62_docs ─► 63_git_merge
```

## 6. Global conventions (all IB docs)
- **Owner:** every doc and every source file has exactly one owning agent (`60`).
- **Source of truth:** every derived statement cites its frozen doc.
- **MUST / SHOULD / MAY:** RFC-2119. **MUST** = invariant; violating it fails a merge gate.
- **INV-x:** numbered invariant (defined in `02`, `14`, `42`) that tests must verify.
- **Determinism first:** anything deterministically computable MUST NOT call an LLM.
- **Fail closed:** on ambiguity or error, reject + log; never guess, never proceed.
