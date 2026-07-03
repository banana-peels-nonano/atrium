# 42 — STATE MACHINE (FORMAL)
## States, transitions, guards, invariants — the spine of Charter House
**Owner:** Lifecycle Agent (A4) · **Source of truth:** Lifecycle (frozen), Stress Test, Revision Register v1.1 · **Status:** authoritative

> This is the formal, implementation-ready definition. The Lifecycle Engine (S5) implements exactly this and nothing more. Every transition below is the *complete* legal set; anything not listed is illegal and MUST be rejected + logged.

## 1. States
**Factory loop:** `CAPTURED, FRAMED, PARKED, PARKED_SHOVEL_READY, VALIDATING, SHAPING, BUILDING, LAUNCHED, EARNING, GRADUATED`
**Terminal/holding:** `KILLED, ARCHIVED`
**Alumni (out of factory WIP):** `SCALING, HARVEST, EXITED`

## 2. Slot-consuming states + WIP limits (INV-SM-2)
| State | WIP limit | Slot type |
|---|---|---|
| VALIDATING | ≤ 3 | validating slot |
| SHAPING | = 1 | on-deck slot |
| BUILDING | ≤ 1 | build slot |
| HARVEST (alumni) | ≤ 3 | alumni-capacity |
Overflow when a slot is full: FRAMED→(no validating slot)→`PARKED`; VALIDATING-passed→(SHAPING full)→`PARKED_SHOVEL_READY` (stamped with evidence TTL).

## 3. Transition table (the complete legal set)
| From | To | Guard (all MUST hold) | Auth | Express? |
|---|---|---|---|---|
| CAPTURED | FRAMED | Scout brief exists, ≥2 primary quotes cited | internal | n/a |
| CAPTURED | KILLED | duplicate / known dead-pattern | gate | n/a |
| FRAMED | VALIDATING | score ≥18 (or logged override) AND gut-yes AND validating slot free | **gate, slot** | **no** |
| FRAMED | PARKED | score ≥18 but no slot | internal | n/a |
| FRAMED | KILLED | score <14 or dead-pattern | gate | n/a |
| PARKED | VALIDATING | slot frees + re-admit | **gate, slot** | **no** |
| PARKED | ARCHIVED | stale/superseded (backlog hygiene) | internal | n/a |
| VALIDATING | SHAPING | Evidence sub-gate PASS AND Experiment sub-gate PASS AND SHAPING free | gate | yes (non-slot? SHAPING is slot=1 → **no**) |
| VALIDATING | PARKED_SHOVEL_READY | both sub-gates PASS but SHAPING occupied | internal | n/a |
| VALIDATING | KILLED | evidence bar failed OR experiment threshold missed OR unreachable | gate (Fri) | n/a |
| PARKED_SHOVEL_READY | SHAPING | SHAPING free AND evidence age ≤ TTL (else re-confirm first) | gate | no |
| PARKED_SHOVEL_READY | VALIDATING | evidence age > TTL → mini re-validation | gate | no |
| SHAPING | BUILDING | spec approved AND ≤10 active-days AND build slot free | **gate, slot** | **no** |
| SHAPING | VALIDATING | can't fit after 2 cuts | gate | n/a |
| SHAPING | KILLED | not buildable small enough | gate | n/a |
| BUILDING | LAUNCHED | 5 design partners complete loop unassisted | gate | n/a |
| BUILDING | KILLED | >15 active-days OR partners silent | gate | n/a |
| LAUNCHED | EARNING | ≥10 activated AND payment-intent in window | gate | yes (non-slot) |
| LAUNCHED | KILLED | activation <20% after 2 fixes OR flat retention | gate (Fri) | n/a |
| LAUNCHED | (pivot) | founder pivot → KILL + FORK (see §5) | gate | n/a |
| EARNING | GRADUATED | $1k MRR or 10 payers in 60 active-days AND alumni-capacity < cap | **gate, alumni-slot** | no |
| EARNING | KILLED | churn>15%/mo after fixes OR CAC>6mo-LTV OR heroics-only | gate (Fri) | n/a |
| EARNING | (pivot) | founder pivot → KILL + FORK | gate | n/a |
| GRADUATED | SCALING | founder graduates | gate | n/a |
| SCALING | HARVEST | steady state (HARVEST cap ≤3) | gate | n/a |
| SCALING | EXITED | sold/wound down | gate | n/a |
| HARVEST | EXITED | sold / no-zombie rule | gate | n/a |
| KILLED | ARCHIVED | salvage complete (≥1 asset banked) | internal | n/a |

## 4. Guard rules (INV-SM-1,3,4,6)
- **INV-SM-1:** any (from,to) not in §3 → reject+log. No exceptions.
- **INV-SM-3 (clocks):** all deadlines measured in **factory-active time** accumulated from `experiment_live_at` (set at first send/traffic), never wall-clock, never from state entry. `pause` freezes accumulation; `resume` restarts.
- **INV-SM-4 (express):** `advance.express` is permitted ONLY for transitions marked "Express? yes" — i.e., non-slot-consuming (LAUNCHED→EARNING). Any slot-consuming transition (→VALIDATING, →SHAPING, →BUILDING, →GRADUATED) MUST occur at a deliberate gate.
- **INV-SM-6 (TTL):** `PARKED_SHOVEL_READY` evidence older than the configured TTL (default 60 active-days) MUST require a re-confirmation signal before BUILDING.

## 5. Pivot (INV-SM-5) — kill-and-fork
`pivot(v)`: (1) check ledger for an existing fork in v's lineage → if present, REFUSE (max one fork/lineage; a second pivot must clear a fresh full validation as a new lineage). (2) `KILL v` + run salvage. (3) auto-`CAPTURE` a new venture with `forked_from = v`, inheriting the audience list + validated-segment record (NOT the dead value prop). (4) free v's slots. (5) the fork enters at `FRAMED` for re-scoring; it does NOT jump the backlog.

## 6. Registry record (per venture)
`id, codename, state, score, forked_from?, state_entered_at, experiment_live_at?, active_time_accum, omw_granted?(bool), evidence_ttl_at?, artifact_links[], event_stream_ptr`. "Current state" is a projection; authoritative state = replay of the ledger (INV-LEDGER).

## 7. Invariants summary (tested in `54`/`55`)
INV-SM-1 legality · INV-SM-2 WIP/slots · INV-SM-3 active-time clocks · INV-SM-4 express restriction · INV-SM-5 pivot fork cap · INV-SM-6 evidence TTL. All six MUST have named passing tests before S5 is Done.
