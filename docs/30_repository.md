# 30 — CODE REPOSITORY LAYOUT & MODULE BOUNDARIES
**Owner:** Program · **Source of truth:** Repository Architecture (frozen), `50` · **Status:** authoritative

## Principle
One code module per subsystem; module boundaries == subsystem boundaries == ownership boundaries (`60`). Imports follow the anti-coupling rules (`43` §5/§8).

## Module tree (Python package `charterhouse/` + repo dirs)
```
K:\the_charter_house\
├── charterhouse\                 # the Python package (deterministic core + router + memory)
│   ├── env\            (A1, S2)
│   ├── config\         (A2, S3)
│   ├── ledger\         (A3, S4)
│   ├── registry\       (A3, S4)
│   ├── lifecycle\      (A4, S5)
│   ├── governance\     (A5, S6)
│   ├── security\       (A5, S7)
│   ├── router\  + router\adapters\   (A6, S8)
│   ├── memory\         (A7, S9)
│   ├── capabilities\framework\       (A8, S10)
│   ├── conductor\      (A10, S12)
│   ├── projections\    (A10, S13)
│   ├── logging\        (A11, S14)
│   └── contracts\      (Interface Agent — shared types, imported everywhere)
├── agents\             (A9, S11 — neutral capability specs *.agent.md)
├── adapters\harness\   (A8 — opencode\, claude-code\, aider\ generators)
├── config\             (A2 — providers/models/routes/profiles yaml)
├── vault\              (runtime data; not code)
├── data\ledger\        (runtime truth; not code)
├── templates\          (Builder templates; built in impl)
├── tests\              (A11, S15)
├── docs\               (this Implementation Bible + frozen design docs)
└── scripts\            (ops; built in impl)
```

## Import law (enforced in CI — `43` §8)
- `contracts\` imports nothing internal (leaf).
- Deterministic modules (`env, config, ledger, registry, lifecycle, governance, security, projections, conductor, logging`) MUST NOT import LLM-path modules (`router, memory, capabilities`) — except `conductor` and `capabilities/framework`, which may import interfaces to orchestrate. Concretely: `lifecycle` must not import `router`; `governance` must not import `capabilities`; etc. The exact allowed edges are the DAG in `52` §1.
- Everyone imports `contracts\` for shared types; no one redefines a shared type.

## One-owner rule
Each directory has exactly one owning agent (table above). A PR touching a directory not owned by its agent fails the merge gate (`60`, `63`).

## Venture product code
Graduated ventures get **separate `venture-<slug>` repos** — never inside this repo (frozen Repository Architecture). This repo is the factory, not the products.
