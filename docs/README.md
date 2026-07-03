# Charter House — Implementation Bible
**The permanent engineering specification. Read this first.**

This repository is consumed by Claude Code to implement Charter House. The product architecture is **frozen** (Charter House v1.1); nothing here changes it. These documents remove every ambiguity between "the design" and "the code," so implementation is a matter of *engineering discipline*, not *architectural reasoning*.

## Start here (in order)
1. **`00_manifest.md`** — the index, the ownership map, and the document dependency graph.
2. **`70_claude_code_execution_plan.md`** — exactly how you (Claude Code) execute this package: what to read, which agent starts, how work is scheduled, how merges gate, how to resume after interruption.
3. **`50_engineering_decomposition.md`** → **`52_dependency_graph.md`** → **`53_build_phases.md`** — the plan.

## The rules that override everything
- **Architecture is immutable.** Implement as written. Raise a *Blocking Impossibility* only for physically un-implementable specs (`70` §Failure handling). Never silently redesign.
- **Contracts before code.** No subsystem is implemented until its four contract documents (`IMPLEMENTATION.md`, `API.md`, `TESTPLAN.md`, `RISKS.md` — templates in `56`) exist and are internally consistent.
- **Tests before implementation.** You never implement functionality without knowing how it is validated (`55`).
- **Every merge is production-quality.** All merge gates in `63` must pass: contracts valid, lifecycle invariants hold, docs updated, tests pass, interfaces compatible, security + PII routing preserved, acceptance criteria met.
- **One owner per file.** No overlapping ownership (`60`).
- **Determinism first, fail closed.** Deterministic logic never calls an LLM; on ambiguity, reject and log.

## What Charter House is (one paragraph, for orientation only)
A solo-founder "startup factory": a deterministic **Conductor** engine moves **Ventures** through a **state-machine lifecycle**; stateless **Capabilities** (LLM-backed: Scout, Analyst, Builder, Growth, Librarian, + Critic mode) do the judgment-heavy work; an append-only **Ledger** records everything and a tiered **Memory** compounds knowledge; a **Governance** layer ensures nothing spends money, deploys, contacts people, or leaks PII without explicit human authorization; a **Router** makes every model/provider swappable via config. The full framing is in `01`–`05`.

## Repository conventions
See `00_manifest.md` §6. In short: RFC-2119 MUST/SHOULD/MAY, numbered invariants `INV-x`, single ownership, cite-your-source, fail closed.

## Status
IB-1.0 · architecture baseline Charter House v1.1 (frozen) · ready for Phase 0.
