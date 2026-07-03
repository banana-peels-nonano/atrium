# 21 — INSTALLATION (setup the code depends on)
**Owner:** Environment Agent (A1) · **Source of truth:** Environment Specification (frozen), Parts 8 & 10

## Scope of this doc
The code does not perform system installation; the founder does (Env Spec Part 8). This doc defines the **preconditions the code checks** and the **install-order guarantees** it relies on. A1 implements checks, not installers.

## Preconditions the code verifies (mirror of Env Spec Part 10 "Claude Code Ready")
- Software: Git+Bash, Python 3.12 (uv), Node LTS, OpenCode, Ollama (running), LanceDB (pip in venv). VS Code Portable optional.
- Env vars: all machine-level redirections set (`25` §1) BEFORE any model pull.
- Models: `nomic-embed-text` pulled to `K:\Models\ollama`; ≥1 reasoning/coding/critic route resolvable.
- Storage: K: paths present; C: ≥ ~20 GB after install; vectors dir read/writeable.
- Keys: provider keys in `.env` (gitignored); `.env.example` committed.

## Ordering guarantees the code assumes
1. `OLLAMA_MODELS` is set before the first pull (else weights waste C:).
2. Embedding model pulled before any LLM (validates the pipeline cheaply).
3. Caches (pip/npm/hf/uv) redirected to K: before installs generate them.
The code's preflight (`20`) asserts the *result* of this order; it does not enforce the order itself.

## Failure handling
Any unmet precondition → preflight fails closed with the specific remediation (referencing the Env Spec step). The code never attempts to auto-install or auto-download beyond a pinned embedding pull it may offer as an explicit, logged action.

## Acceptance
Preflight on a "Claude Code Ready" machine passes; on a machine missing any single item, the exact item is named.
