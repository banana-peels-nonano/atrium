# Charter House

A deterministic **solo-founder startup factory**. A rule-based **Conductor** walks
**Ventures** through a formal state-machine lifecycle; stateless, LLM-backed
**Capabilities** do the judgment-heavy work but hold no authority; an append-only
**Ledger** is the single source of truth (all state/boards/metrics are regenerable
projections); a tiered **Memory** compounds knowledge; a **Governance + Security**
layer ensures nothing spends money, deploys, contacts a person, crosses a lifecycle
gate, or leaks PII without explicit human authorization; a **Router** makes every
model/provider swappable via config.

> **Architecture is frozen (Charter House v1.1).** This repository is built strictly
> to the specification in [`docs/`](docs/) (the Implementation Bible). The build does
> not redesign the architecture — see [`docs/README.md`](docs/README.md) and
> [`docs/00_manifest.md`](docs/00_manifest.md).

## Non-negotiable build rules
- **Architecture is immutable** — implement as written; raise a *Blocking Impossibility*
  only for physically un-implementable specs (`docs/70` §Failure handling).
- **Contracts before code** — no subsystem is implemented until its four contract docs
  (`IMPLEMENTATION/API/TESTPLAN/RISKS`, templates in `docs/56`) exist and are consistent.
- **Tests before implementation** (`docs/55`).
- **Every merge is production-quality** — all 10 merge gates in `docs/63` pass. Never merge red.
- **One owner per file** (`docs/60`).
- **Determinism first, fail closed** — deterministic logic never calls an LLM; on
  ambiguity, reject and log. PII never reaches a cloud model (`docs/24`).

## Layout
See [`docs/31_folder_structure.md`](docs/31_folder_structure.md). In short: `charterhouse/`
(subsystem packages), `config/`, `vault/`, `data/`, `agents/`, `templates/`, `tests/`,
`docs/` (the Implementation Bible + frozen design docs), `scripts/`.

## Environment & dependencies
- Requires Python ≥ 3.13, `uv`, and `git`.
- **Storage discipline:** nothing on C:. Tools → `K:\Tools`; caches → `K:\Data\charter_house\cache`;
  model weights → `K:\Models`; project venv → `.venv` (gitignored, drawing from the shared K: cache).
  Set the machine-level redirections from `.env.example` via `setx` and verify before installing anything.
- Copy `.env.example` → `.env` and fill provider keys (`.env` is gitignored).

## Build status
Phase 0 (A0 Scaffold). See [`docs/BUILD_TRACKER.md`](docs/BUILD_TRACKER.md) for the
append-only build ledger and current phase.
