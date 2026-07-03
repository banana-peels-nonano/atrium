# 31 — EXACT FOLDER STRUCTURE (created by A0 scaffold)
**Owner:** Environment Agent (A1) / Scaffold Agent (A0) · **Source of truth:** Repository + Environment Architecture (frozen)

> The Scaffold Agent (A0) creates this tree in Phase 0. The structure test asserts the tree matches this doc exactly. Runtime folders (vault ventures, ledger events, backups) are created on demand by their owning subsystem, not by scaffold.

```
K:\the_charter_house\
├── README.md
├── AGENTS.md                      # generated (harness-neutral constitution pointer)
├── .gitignore                     # .env, *.private.md, caches, Models/, Data/, Logs/, __pycache__
├── .env.example
├── pyproject.toml                 # uv/py project (A0)
├── charterhouse\
│   ├── __init__.py
│   ├── contracts\   __init__.py
│   ├── env\         __init__.py  IMPLEMENTATION.md API.md TESTPLAN.md RISKS.md
│   ├── config\      (same 4 contract docs + __init__)
│   ├── ledger\      ( … )
│   ├── registry\
│   ├── lifecycle\
│   ├── governance\
│   ├── security\
│   ├── router\      + adapters\
│   ├── memory\
│   ├── capabilities\framework\
│   ├── conductor\
│   ├── projections\
│   └── logging\
├── agents\                        # scout.agent.md analyst… (A9; empty stubs at scaffold)
├── adapters\harness\opencode\
├── config\
│   ├── providers.yaml
│   ├── models.yaml
│   ├── routes.yaml
│   └── profiles\ free.yaml cheap-cloud.yaml local-first.yaml
├── vault\
│   ├── inbox\
│   ├── ventures\                  # <slug>\ created at runtime
│   ├── memory\ lessons\ playbooks\
│   ├── archive\
│   └── PIPELINE.md                # generated
├── data\
│   ├── ledger\                    # append-only events (runtime)
│   └── metrics\ METRICS.md        # generated
├── templates\ landing\ saas-starter\
├── tests\
│   ├── fixtures\ fakes\ (FakeProvider, FakeEmbedder, Clock, pii_corpus, golden_set)
│   ├── unit\ integration\ simulation\ invariants\
│   └── conftest.*                 # harness wiring
├── docs\                          # this Implementation Bible + frozen design docs
└── scripts\                       # built during implementation
```

## MUST
- Every subsystem folder ships its four contract docs (`56`) at scaffold — empty but present.
- `.gitignore` excludes: `.env`, `**/*.private.md`, `**/__pycache__`, `K:\Models`, `K:\Data`, `K:\Logs` (external anyway), local caches.
- The tree is verified by a structure test (`54` A0); drift fails CI.
