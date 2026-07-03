# 52 — DEPENDENCY GRAPH
## Build order DAG · parallelism · critical path · merge-conflict avoidance
**Owner:** Program · **Source of truth:** `50`, `51` · **Status:** authoritative

---

## 0. Reading this graph
Nodes are subsystems (S1–S15 / agents A0–A11). An edge `X → Y` means **Y cannot start until X's *contracts and interfaces* are frozen** (not necessarily its full implementation). Because subsystems depend on *interfaces* (`43`), not implementations, much work parallelizes once interfaces are agreed. "Frozen interface" is the unlock, and it happens at each subsystem's contract stage (`56`), early.

## 1. The DAG
```
A0 Scaffold
  ├─► A2 Config ───────────────┐
  ├─► A1 Environment            │
  ├─► A11 Test/Logging (parallel, always-on)
  └─► A3 Ledger/Registry ──────┼─► A4 Lifecycle ──────────────┐
                               ├─► A5 Governance/Security ─────┤
                               │        └─(sec/pii)─► A6 Router ┤
                               │                                │
                        A2 ────┴─► A6 Router ───────────────────┤
                        A3+A5+A6 ─► A7 Memory ──────────────────┤
              A4+A6+A7+A5 ─────────► A8 Capability Framework ────┤
                        A8 ────────► A9 Capability Content ──────┤
   A2..A9 ────────────────────────► A10 Conductor + Projections ─┘
```

## 2. What can start immediately (Wave 0 — no dependencies but A0)
- **A0 Scaffold** (must finish first — everyone needs the tree).
- Then, in parallel: **A1 Environment**, **A2 Config**, **A3 Ledger/Registry**, **A11 Test/Logging**. These four share no files and depend only on the scaffold + interface docs. Maximum early throughput.

## 3. What unlocks next (Wave 1 — after A3 interface frozen)
- **A4 Lifecycle** (needs Ledger/Registry API).
- **A5 Governance/Security** (needs Ledger API + Config).
These two are **independent of each other** (disjoint files) → parallel.

## 4. Wave 2 (after A2 + A5 interfaces frozen)
- **A6 Router** (needs Config + Security's `contains_pii` tag).

## 5. Wave 3 (after A3+A5+A6)
- **A7 Memory** (needs Ledger + Security + embeddings via Router/Ollama).

## 6. Wave 4 (after A4+A6+A7+A5)
- **A8 Capability Framework** (the 5-beat runner needs Lifecycle, Router, Memory, Security).

## 7. Wave 5
- **A9 Capability Content** (needs the framework).

## 8. Wave 6 (integration)
- **A10 Conductor + Projections** (binds A2–A9). Last, by design — it is the thin integrator.

## 9. Critical path (longest dependency chain)
```
A0 → A3 → A4 → A8 → A9 → A10
A0 → A3 → A5 → A6 → A7 → A8 → A9 → A10   (the true critical path: memory + framework)
```
The critical path runs **through Security/Router/Memory into the Capability Framework**. Optimization: freeze A5/A6/A7 *interfaces* as early as possible (contract stage) so A8 can begin against stubs while A5–A7 finish implementations. A11 (tests) shadows the whole path and is never on the critical path because it starts at A0.

## 10. Parallelism map (max concurrent workstreams)
| Wave | Concurrent agents | Shared files? | Merge-conflict risk |
|---|---|---|---|
| 0 | A1, A2, A3, A11 (after A0) | none | ~zero |
| 1 | A4, A5 | none | ~zero |
| 2 | A6 (+ A4/A5 finishing) | none | ~zero |
| 3 | A7 | none | ~zero |
| 4 | A8 | none | low (imports interfaces) |
| 5 | A9 | none | ~zero (data files) |
| 6 | A10 | integrates, owns own files | low (interface-only imports) |

Merge conflicts are structurally near-zero because **ownership is disjoint** (`60`) and dependencies are on **interfaces**, not code. The only integration-time risk is at A10; mitigated by A10 importing frozen interfaces (`43`) and owning only its own files.

## 11. What must wait (hard blocks)
- No capability (A8/A9) may run before **Governance+Security (A5)** exists — otherwise the PII/authorization guarantees don't hold. **Hard block.**
- No **Memory (A7)** before **Security (A5)** — embeddings must not touch raw PII. **Hard block.**
- No **Conductor (A10)** integration test with real spend/send/deploy — *ever* in this build; only dry-runs (`55`). **Permanent block.**

## 12. Interface-freeze milestones (the real unlocks)
The schedule (`70`) tracks **interface-freeze**, not completion:
1. IF-1: Ledger/Registry + Event catalog (`41`) frozen → unlocks A4, A5, A7.
2. IF-2: Config + Router `LLMClient` signature frozen → unlocks A7, A8 stubs.
3. IF-3: Security redaction/scan/tag signatures frozen → unlocks A6 pii-path, A7.
4. IF-4: Lifecycle transition API + `42` invariants frozen → unlocks A8, A10.
5. IF-5: Workflow runner signature frozen → unlocks A9, A10.
