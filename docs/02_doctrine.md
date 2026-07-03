# 02 — DOCTRINE (as machine-checkable invariants)
**Owner:** Program · **Source of truth:** Doctrine (frozen) · **Status:** authoritative

> The founding doctrine, restated as invariants the software MUST enforce. Each maps to a test (`55`). These are the highest-priority correctness constraints; a violation is a failed merge (`63`).

## The non-negotiable rules → invariants
| Doctrine rule | Invariant | Owner subsystem | Test tier |
|---|---|---|---|
| No money/deploy/contact without founder authorization | `INV-GOV-1` every RED action requires a valid token | S6 | governance |
| WIP limits are absolute | `INV-SM-2` validating ≤3, SHAPING =1, building ≤1, HARVEST ≤3 | S5 | state-machine |
| Every kill banks an asset | `INV-SALVAGE` `kill`→`salvage` with ≥1 asset type | S12/S9 | integration |
| Advance/kill decisions only at the weekly gate | `INV-GATE-CADENCE` kills only via Friday gate; express = advance-only, non-slot | S5/S12 | state-machine |
| Inconclusive = fail | `INV-VERDICT` inconclusive experiment ⇒ FAIL default | S5 | state-machine |
| Secrets/PII never leave local unless flagged | `INV-PII-1..4` redaction + scan + cloud-block + gitignore | S7/S8 | security |

## Derived engineering laws (from doctrine philosophy)
- **Determinism first (`INV-DET`):** anything computable deterministically MUST NOT call an LLM. The Conductor, lifecycle, governance, security, ledger, projections are LLM-free. Enforced by the anti-coupling/import test (`43` §8) — LLM-path modules must not be imported by deterministic ones.
- **Fail closed (`INV-FAILCLOSED`):** on ambiguity, error, or missing authorization, reject + log; never guess, never proceed.
- **One source of truth (`INV-LEDGER`):** the append-only ledger is reality; all boards/metrics/state are regenerable projections.
- **Attention economy (`INV-TRIAGE`):** human-facing output (Daily Brief) is triaged to the few decisions that need a human today; the system never dumps raw work on the founder.

## Enforcement summary
Every row above has a named test in the invariant harness (`55` §4). The phase-exit gate (`53`) refuses to pass if any doctrine invariant lacks a passing test. Doctrine is thus not a document the code "respects" — it is a set of red/green checks.
