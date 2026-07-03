# 20 — ENVIRONMENT (runtime assumptions for code)
**Owner:** Environment Agent (A1) · **Subsystem:** S2 · **Source of truth:** Environment Specification (frozen)

## Runtime facts the code MUST assume (and verify at preflight)
- **OS:** Windows 11. **Repo root:** `K:\the_charter_house`. **Storage law:** everything relocatable on `K:`; `C:` is ~25 GB, treat as nearly full.
- **Language:** Python 3.12+ (deterministic core, router, memory), config in YAML, harness = OpenCode (Node). Derived-frozen from Env Spec.
- **Default posture:** REMOTE-FIRST. Heavy roles → free cloud tiers behind the Router; only embeddings + vector store run locally.
- **Local model server:** Ollama (OpenAI-compatible `/v1`), weights on `K:\Models\ollama`.
- **Vector store:** LanceDB (embedded, files on `K:\Data\charter_house\vectors`). No Docker in base.
- **Embedding model:** `nomic-embed-text` (frozen; changing it = guarded re-index).

## Preflight (deterministic; fail closed)
A1 implements a preflight that MUST verify, each with one precise error on failure:
1. Required env vars present (`25`).
2. K: paths exist + writable; C: headroom ≥ threshold.
3. Local embedding endpoint reachable (Ollama up, model pulled).
4. Vector store path initialized.
5. At least one model route resolvable for each role (per active profile).
Preflight produces an immutable `EnvContext` (paths, profile, endpoints); no subsystem reads env directly.

## MUST
- No code reads environment variables except through `EnvContext` (A1).
- Missing prerequisite → fail closed with an actionable message; never partial-boot.
- The code must run with **zero** paid cloud dependency on the default `free` profile (local embeddings + free tiers only).

## Acceptance
`54` S2/Global; preflight pass on a prepared machine; each failure mode → exactly one precise error.
