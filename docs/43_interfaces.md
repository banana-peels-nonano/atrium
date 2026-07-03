# 43 — INTERFACE BOUNDARIES & VERSIONING
## How subsystems depend on each other without coupling
**Owner:** Interface Agent · **Source of truth:** `40`, `50` · **Status:** authoritative

> Principle: **subsystems depend on interfaces, never on implementations.** This is what makes the parallel build in `52` safe and future rewrites cheap (priority #4). This doc defines *how* interfaces are declared, stubbed, frozen, and changed.

## 1. Interface declaration
Every subsystem's public surface is declared in its `API.md` (`56`) and must match `40` exactly. The interface = signatures + preconditions + postconditions + error contract + determinism class + (if it triggers an action) authorization class. Nothing public exists that isn't in `API.md`.

## 2. Stubbing for parallelism
Before a partner subsystem is implemented, an agent generates a **stub** from the frozen `40` signature (a typed no-op / canned-response double, provided by the Test harness A11). Agents build against stubs, then swap to the real implementation when the partner's interface-freeze milestone (`52` §12) is reached. **No agent waits on another's implementation — only on its interface-freeze.**

## 3. Interface-freeze milestones (the unlocks)
Repeated from `52` for enforcement here:
- IF-1 Ledger/Registry + Event catalog (`41`)
- IF-2 Config + `LLMClient.call` signature
- IF-3 Security redact/scan/tag signatures
- IF-4 Lifecycle transition API + `42` invariants
- IF-5 Workflow runner signature
A milestone is "frozen" when its `API.md` is reviewed by Program and recorded in the build tracker (`70`). After freeze, changes follow §4.

## 4. Changing a frozen interface (breaking change protocol)
1. The proposing agent files an **Interface Change Request (ICR)** describing the change, the reason, and every consumer affected (from `40`/`43` consumer lists).
2. It is *not* an architecture change — if it were, it's a Blocking Impossibility (`70`) instead. ICRs are engineering-level only.
3. All consuming agents sign off (their `API.md` "consumed surface" updated).
4. The interface version is bumped; a migration note is written; stubs + tests updated in the same PR.
5. Merge only when every consumer's tests pass against the new signature.
No frozen interface changes silently. A PR that alters a `40` signature without an ICR fails the merge gate (`63`).

## 5. Boundary rules (MUST) — restated for enforcement
- Lifecycle (S5) exposes only state/guard operations; it imports nothing from Router/Memory/Capabilities.
- Governance (S6) and Security (S7) expose classify/authorize/redact/scan/tag; they never call an action.
- Router (S8) exposes `call`; it imports Config + Security(tag) + Ledger(telemetry) only. No role logic.
- Memory (S9) exposes retrieve/write/consolidate/reindex; imports Ledger + Security + Embeddings.
- Capabilities (S11) expose `produce`; import nothing that grants authority.
- Conductor (S12) imports every subsystem interface but re-implements no rule (INV-COND-1).

## 6. Data contracts (shared types)
Shared types (`Event`, `Venture`, `State`, `Token`, `AuthClass`, `LLMResponse`, `WorkingSet`, `GateBrief`, `Route`, `Model`) are defined once in a `contracts/` types module owned by the Interface Agent and imported everywhere. **No subsystem redefines a shared type.** Changing a shared type is an ICR (§4).

## 7. Versioning scheme
- Interface version: integer per subsystem, bumped on breaking change.
- Event `schema_version`: additive changes don't bump consumers; removals/renames do (migration required).
- The `contracts/` module carries the aggregate interface version recorded in the build tracker.

## 8. Anti-coupling test (enforced in CI)
A static check asserts the import graph matches §5 (e.g., `lifecycle/` must not import `router/`). A violating import fails the merge gate. This makes the boundaries *mechanically* enforced, not merely documented.
