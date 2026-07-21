# Conductor (S12) — IMPLEMENTATION
Owner: A10 Conductor Agent   Subsystem: S12   Source of truth: docs/10 (build contract) + docs/40 §8 + docs/05 (levers/hard rules) + docs/54 §S12 / docs/55

## 1. Responsibility (one paragraph)
S12 is the deterministic integrator and single chokepoint: every founder/system action
enters as ONE `Conductor.command`, is classified by S6, guarded and acted by its OWNING
subsystem, recorded on the ledger, and reflected in regenerated S13 projections. It
MUST NOT: own any rule of S5/S6/S7 (INV-COND-1 — legality tables, the class matrix,
token semantics, PII rules all stay where they live; the conductor only carries calls
and tokens), hold durable state between commands (INV-COND-3 — the ledger is the only
memory), execute any external effect without the correct-class token (and in v1 no
real deploy/billing/send/launch effect exists at all — the authorization boundary is
the end of the line, INV-TEST-SAFE), or present a gate without a critic take
(INV-COND-2, via S13's fail-closed brief).

## 2. Invariants enforced
- **INV-COND-1** — no S5/S6/S7 rule re-implemented. Guaranteed structurally: the
  dispatch table maps command → owner call; tokens pass through to S5's boundary
  (consumed exactly once, by S6, inside S5's `_authorize`); S6-owned commands call
  `Gov` directly; refusal reasons are always the owner's text. Verified by (a) a
  static test — no classify matrix, no transition-legality data, no `AuthClass`
  construction, no PII regex under `conductor/` — and (b) call-path spy tests: every
  guarded command's decision provably transits the owner.
- **INV-COND-2** — every Gate Brief conforms to the fixed `GateBrief` schema and
  includes the Critic field. Guaranteed by construction in S13 (`GateBrief.critic` is
  a required `CriticTake`; assembly raises `NoCriticForGate` when none exists) and by
  the `gate` command consuming the brief (its `gate_decision` carries `critic_tier`).
- **INV-COND-3** — crash mid-command → replay reconstructs state, zero loss.
  Guaranteed by: no conductor field mutates between commands (stateless dispatch over
  injected live seams); every durable fact is ONE atomic `Ledger.append` (S4);
  projections are pure re-derivations. Tested by rebuilding a fresh Conductor over
  the same ledger dir mid-sequence and by a probe that kills the recorder append.

## 3. Internal design
Modules under `charterhouse/conductor/`:
- `types.py` — `CommandResult` + the error taxonomy (`ConductorError`,
  `CommandRefused`, `NoCriticForGate`).
- `dispatch.py` — `Conductor`: the wiring constructor (live seams injected: ledger,
  registry, lifecycle, gov, memory, workflow, projections, clock) + `command()`
  implementing the 5-step pipeline + one small handler per command (call-through
  only; recorder-fact payload builders live here and validate SHAPE only — e.g.
  salvage's ≥1 asset type, a docs/41 payload rule, not an S5/S6/S7 rule).
- `workflows.py` — the REAL state→workflow table (docs/13 rows: scout/analyst/
  builder/builder/growth) checkpointing `artifact_produced`; built on A8's
  `WorkflowRegistry` (which re-validates no-authority at construction).
`charterhouse/contracts/events.py` gains the **additive** `ARTIFACT_PRODUCED` member
(docs/41 §2 updated in the same PR — docs/62 rule).
**Durable state: none.** The ledger is the only memory; the Registry is S4's
projection; S13 re-derives on every read.

## 4. Dependencies
The full live stack, by frozen surface only: S4 `Ledger.append/read` + `Registry.get`
(IF-1); S5 `transition/pivot/grant_omw/pause/resume/slots/clock` + typed errors
(IF-4); S6 `classify/authorize/envelope_open/spend/grant/record_override` (IF-3);
S7 via S10's CHECKPOINT (IF-3); S8 behind S10 (IF-2); S9 `consolidate` + (behind S10)
`retrieve/write_lesson`; S10 `Workflow.run` (IF-5); S13 projection functions; S14
`Log`. A11 fakes at test time only (`FakeProvider`, `FakeEmbedder`, probes).

## 5. Failure behavior
Every refusal is fail-closed, typed, with the OWNER's reason, and pre-act refusals
leave the ledger untouched:
- Unknown command → RED classify + S6 denial → `CommandRefused`.
- Missing/wrong-scope/expired/consumed token → the owner's denial (S6 text via S5's
  typed error or Gov's `Decision.reason`) → `CommandRefused`.
- Guard failures (slots, sub-gates, windows, TTL) → S5's typed errors wrapped in
  `CommandRefused` (message preserved verbatim).
- Two-key without a passing check → S6 denial (INV-GOV-2) → `CommandRefused`.
- Malformed recorder payload (e.g. empty salvage `asset_types`) → `CommandRefused`
  naming the field; nothing appended.
- Gate without a critic take → `NoCriticForGate` (INV-COND-2); nothing appended.
- A crash between an owner's append and a follow-up recorder append loses nothing:
  the appended history IS the truth; replay reconstructs it (INV-COND-3 probe test).

## 6. Open questions → RESOLVED
1. **Double consumption of single-use tokens.** `Gov.authorize` consumes on ok; S5
   also authorizes inside `transition`. RESOLVED: for S5-owned commands the conductor
   NEVER pre-authorizes — it classifies (pure) and passes the token through; S5's
   boundary is the single consumption point. S6-owned commands authorize directly.
   One token, one consumption, always at the owner.
2. **Where does `spec_approved` come from?** docs/05: cut-list → `spec_approved`
   (gate); the S5 SHAPING→BUILDING guard requires the fact BEFORE transition; the
   event type requires an authorization id. RESOLVED: `gate(ADVANCE→BUILDING,
   spec_ref=…)` appends `spec_approved{spec_ref, fits_days}` carrying the SAME
   token's id (the ledger checks presence, not consumption), then calls
   `transition` — which consumes that token once at S5. The fact and the advance are
   one founder decision, recorded as two events under one token id.
3. **Which commands run workflows?** The frozen matrix names `shape` and `build`.
   RESOLVED: v1's command surface runs workflows for exactly those; other states'
   workflows remain reachable via the S10 surface (the Conductor-Spec scheduler is
   post-v1). `recruit.partners` records the `partners{recruited_count}` fact
   (R-PARTNERS — the drafts themselves are Growth-capability artifacts under S10).
4. **What event does a workflow checkpoint append under the conductor's table?** The
   docs/41 catalog had no artifact event; misusing `frame`/`evidence_gate` would
   corrupt replay semantics. RESOLVED: additive `artifact_produced{artifact_ref,
   capability, critic_tier}` (IF-1 explicitly allows additive event types; docs/41 §2
   updated in this PR; state-neutral — no `to_state`, replay-inert by construction).
5. **`calibrate` appends nothing?** RESOLVED: yes — it is a pure S13 read (GREEN);
   the docs/41 catalog has no calibration event and none is needed (regenerable).
6. **`deploy.prod`/`billing.enable`/`launch` real effects.** RESOLVED: v1 records the
   authorized decision event and STOPS — no deploy pipeline, no billing switch, no
   send transport exists in this codebase (INV-TEST-SAFE is a permanent test
   invariant and, in v1, a code fact). The events are the integration points the real
   pipelines will consume post-v1.
7. **Mechanical recommendation source for gate/kill-day briefs.** RESOLVED: S13
   derives it from ledger facts only (evidence verdicts, clock windows, slot
   pressure) as ADVANCE/HOLD/KILL — advisory, never enforced; the founder's `gate`
   decision is the authority (docs/05 five levers).
