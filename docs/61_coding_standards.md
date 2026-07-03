# 61 — CODING STANDARDS
**Owner:** Program · **Source of truth:** Environment Spec (language), doctrine (determinism) · **Status:** authoritative

## Language & tooling (derived-frozen from Env Spec)
- **Python 3.12+** for the deterministic core, router, memory. Typed (type hints everywhere; a type checker runs in CI). **uv** for envs (on K:).
- **YAML** for config. **Node/OpenCode** only for the harness adapter layer.
- Formatter + linter + type checker run in CI and pre-commit; a failure blocks merge.

## The determinism rule (highest, `INV-DET`)
- Anything deterministically computable MUST NOT call an LLM. The deterministic modules (`env, config, ledger, registry, lifecycle, governance, security, projections, conductor, logging`) contain **no** model calls. Enforced by the import DAG (`43` §8): these modules cannot import `router`/`memory`/`capabilities`.
- LLM calls exist only in `router` (the client) and are *invoked* only from `capabilities/framework` PRODUCE/CRITIQUE beats.

## Error handling (`INV-FAILCLOSED`)
- Fail closed on ambiguity, error, or missing authorization: reject + structured log; never guess, never partial-proceed.
- No bare excepts that swallow; every caught error is logged with context and either handled by a defined fallback (failover/retry per spec) or re-raised.
- No silent defaults for security/authorization/state — those must be explicit.

## Purity & state
- Deterministic functions are pure where possible; side effects (ledger append, file write) are isolated and explicit.
- Durable state lives only in the ledger (`04`). No hidden module-level mutable state that survives a command (would break `INV-COND-3`).

## Idempotency
- PRODUCE/CRITIQUE and any retryable operation MUST be idempotent (safe to re-run; no state change until CHECKPOINT).

## Naming & structure
- Names match the frozen vocabulary (`02_glossary`/architecture terms): venture, capability, conductor, ledger, gate, GREEN/YELLOW/RED, etc. No synonyms that drift from the spec.
- Public functions match `40` signatures exactly; preconditions/postconditions in docstrings; authorization class noted for action-triggering functions.

## Logging
- Structured logs via `Log` (S14); never log secrets or PII (`24`). Every RED/gate/override/pii-block path logs an auditable line.

## Dependencies
- Minimal, pinned, open-source. Prefer stdlib + the few frozen libs (LanceDB, an HTTP client, a YAML parser, a type checker). New deps → `RISKS.md` note + Program review.

## Tests co-located with the contract
- No implementation merges without the `TESTPLAN.md` tests passing (`55`, `56`). Coverage of the subsystem's `MUST` clauses is 100%.
