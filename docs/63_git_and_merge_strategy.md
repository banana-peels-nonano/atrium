# 63 — GIT & MERGE STRATEGY
**Owner:** Program · **Source of truth:** frozen Git strategy (trunk-based), all IB docs · **Status:** authoritative

## Branching (frozen: trunk-based)
- `main` is always green and deployable-of-the-factory.
- Work on short-lived branches: `feat/<subsystem>-<task>`, ≤2 days, one subsystem per branch (`60`).
- Squash-merge to `main`. Every merge is a **production-quality pull request**.

## The merge gate (ALL must pass — hard)
A branch merges to `main` only if:
1. **Architecture contracts remain valid** — no `40`/`contracts` signature changed without an ICR (`43`); `API.md` matches `40`.
2. **Lifecycle invariants hold** — all `INV-SM-*` tests green (if S5 touched or simulated).
3. **Documentation updated** — subsystem contract docs + any affected IB doc current (`62`); no drift.
4. **Tests pass** — unit + integration + touched invariants; 100% `MUST` coverage for changed code (`55`).
5. **Interfaces remain compatible** — no forbidden import (`43` §8 anti-coupling check); no breaking change without ICR + consumer sign-off.
6. **Security rules preserved** — secret scan clean; `INV-PII-*` tests green if S7/S8/S9 touched.
7. **PII routing compliant** — no code path embeds/cloud-routes raw PII; `contains_pii` block test green.
8. **Acceptance criteria satisfied** — the subsystem's `54` rows demonstrably true via tests.
9. **Ownership respected** — only owned files changed (`60`); manifest ownership consistent.
10. **Determinism preserved** — deterministic modules contain no LLM call (`INV-DET` import check).

A PR failing any gate is not merged. No overrides. (This mirrors the product's own "no advancing on optimism.")

## Review model (Claude Code as orchestrator)
- The authoring implementation agent opens the PR with a filled checklist mapping to the 10 gates.
- A **different** context/agent (or Program) reviews — never self-approve a gate. This mirrors the runtime cross-model Critic: verification comes from a different vantage point.
- The invariant-harness report (`55` §4) is attached; a red invariant blocks merge automatically.

## Commit hygiene
- `vault:`-style prefix for data/doc commits; `feat:`/`fix:`/`test:`/`docs:` for code. Secrets never committed (pre-commit scan).
- Interface-changing commits reference the ICR id.

## Resuming after interruption
- Because `main` is always green and every branch is short-lived, an interrupted build resumes from `main` + the build tracker (`70`): pick the next unblocked workstream (`52`), re-open its branch or start the next task. No long-lived divergent state exists to reconcile.

## Release tagging
- The factory itself: tag phase completions (`phase-0` … `phase-9`). Graduated *ventures* live in their own repos and tag `v*` per the frozen deployment workflow — out of scope for this repo.
