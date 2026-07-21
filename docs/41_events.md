# 41 — EVENT CATALOG (LEDGER)
## The canonical, versioned event vocabulary — the append-only truth
**Owner:** Memory Agent (A3/A7) · **Source of truth:** Memory Architecture, Conductor Spec · **Status:** authoritative

> The ledger is the single source of truth (INV-LEDGER). Every meaningful change is one append-only event. State/registry/projections are all replays of these events. Events are **immutable**; corrections are new events, never edits.

## 1. Common envelope (every event)
```
event_id        : uuid (monotonic-sortable, e.g. ULID)
schema_version  : int (this catalog's version; start 1)
timestamp       : ISO-8601 wall-clock (for humans)
active_time     : factory-active-time counter at emission (for deadlines)
venture_id      : id | null (null for factory-global events)
actor           : "conductor" | "founder" | capability-name | "system"
type            : one of §2
from_state      : state | null
to_state        : state | null
payload         : type-specific object (§2)
authorization   : token_id | null   (present for gate/RED events)
prev_hash       : hash of previous event (tamper-evident chain)
```
Append MUST be atomic and totally ordered (INV-LEDGER). `prev_hash` forms the integrity chain; a break is detected on read and blocks replay (fail closed).

## 2. Event types (canonical set)
Grouped; payload fields listed. Adding a type is a versioned, additive change (`43` interface rules); removing/renaming is a breaking change requiring migration.

### Sourcing & framing
- `capture` — {source, note_ref}
- `frame` — {brief_ref, score{pain,reach,build,money,compound}, reach_is_hypothesis:true}
- `score_override` — {old_score, new_score, reason}  *(founder override; INV-GOV-6)*

### Admission & lifecycle transitions
- `admit` — {slot:"validating"} (gate)
- `transition` — {reason, gate_type:"weekly"|"express"|"internal"}  *(generic; from/to in envelope)*
- `park` / `shovel_ready` — {evidence_ttl_at}
- `omw_grant` — {} *(one per lineage max; INV-SM-5/OMW-LEDGER — replay-checked)*
- `override` — {recommendation, decision, reason} *(admission/advance/kill override; INV-GOV-6)*

### Validation
- `evidence_gate` — {verdict:"PASS"|"FAIL", quote_count, segment_kind:"online"|"offline"}
- `experiment_live` — {channel, experiment_live_at}  *(sets the deadline clock; INV-SM-3)*
- `experiment_result` — {metric, actual, threshold, verdict}

### Money & sending (governance)
- `spend_envelope` — {cap_usd} (RED; INV-GOV-4)
- `spend_meter` — {amount_usd, running_total} (YELLOW)
- `spend_breach` — {attempted, cap} → triggers re-RED
- `send_batch` — {count, audience_tz, per_domain} (RED; founder-wide budget INV-GOV-5)

### Build & release
- `spec_approved` — {spec_ref, fits_days} (gate)
- `partners` — {recruited_count} *(design-partner recruitment; R-PARTNERS)*
- `deploy_prod` — {tag} (RED two-key; INV-GOV-2)
- `billing_enable` — {} (RED two-key; distinct from deploy — R-CHARGE)
- `launch` — {kit_ref} (RED)

### Outcomes & memory
- `gate_decision` — {brief_ref, recommendation, decision, critic_tier} (INV-COND-2)
- `pivot_fork` — {killed_id, new_id, inherited:{audience, segment}} (INV-SM-5)
- `kill` — {reason}
- `salvage` — {asset_types:[anti_pattern|template|dataset|audience|channel]} *(≥1 required; R-SALVAGE-TYPES)*
- `graduate` — {} (alumni-capacity checked)
- `alumni_transition` — {to: SCALING|HARVEST|EXITED}
- `consolidate` — {merged, retired, promoted} *(reversible view; never edits ledger; INV-MEM-3)*
- `lesson_written` — {lesson_id, tags, confidence}
- `artifact_produced` — {artifact_ref, capability, critic_tier} *(a workflow CHECKPOINT's artifact record; state-neutral — never carries from/to_state; ADDITIVE 2026-07-19 per §2's evolution rule, with S12's real state→workflow table)*

### System & telemetry
- `pause` / `resume` — {reason}  *(freezes/restarts active-time; INV-SM-3)*
- `llm_call` — {role, model, provider, tokens{in,out}, cost_usd, latency_ms, critic_tier?}  *(telemetry; INV-ROUTE-4)*
- `pii_block` — {context_ref, attempted_route}  *(a PII context was refused a cloud route; INV-PII-3)*
- `error` — {where, kind, fail_closed:true}

## 3. Projections built from these events (regenerable — INV-COND-3)
- **Registry state** ← replay of `transition`/`admit`/`pivot_fork`/`kill`/`graduate`/…
- **PIPELINE board** ← current states + deadlines (active_time).
- **METRICS** ← counts/rates over `frame`/`experiment_result`/`kill`/`llm_call`/`spend_*`.
- **Calibration report** ← `override`, `evidence_gate` vs outcome, golden-set results.
- **Gate/Daily/Kill-Day Briefs** ← per-venture assembly (Conductor).

## 4. Rules (MUST)
1. Events are append-only and immutable. Corrections = compensating events.
2. Every gate/RED action emits an event carrying its `authorization` token id.
3. `omw_grant` and `pivot_fork` are replay-checked to enforce their once-per-lineage caps.
4. No event payload contains raw PII or secrets (redaction happens before append; INV-PII-1). PII lives only in `*.private.md` sidecars referenced by ref, never inlined.
5. `schema_version` is stamped on every event; the reader supports all prior versions (additive evolution).
