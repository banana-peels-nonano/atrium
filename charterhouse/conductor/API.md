# Conductor (S12) — API
Owner: A10 Conductor Agent   ·   Matches docs/40 §8 exactly (frozen seam)   ·   Built LAST against the fully live stack (IF-1..IF-5 all real; no stubs)

## Exposed surface

### `Conductor.command(name: str, args: Mapping, token: Token | None = None) -> CommandResult`
- **Preconditions:** `name` is a docs/40 §8 command (the S6 matrix vocabulary — the
  conductor never keeps its own copy); `args` carries the command's params
  (venture_id, payloads, refs); `token` is a founder authorization where the class
  demands one.
- **Postconditions — the single chokepoint pipeline, per command, in order (docs/10):**
  1. **classify** via `Gov.classify(Action(name, …))` — informational + fail-closed
     (an unknown name is RED and will be denied downstream; the conductor holds no
     matrix).
  2. **enforce guards** via the OWNING subsystem — never locally (INV-COND-1):
     transitions pass the token THROUGH to `Lifecycle.transition/pivot/grant_omw`
     (S5 authorizes at its boundary via S6 — the single-use token is consumed exactly
     once); S6-owned commands call `Gov.envelope_open/spend/authorize`; PII stays
     behind S7 wherever text lands (the S10 CHECKPOINT path).
  3. **act via the owning subsystem** (call-through table below).
  4. **append event** — the acting subsystem appends its own event where it owns one
     (S5 transitions, S9 consolidate); the conductor appends only *recorder* facts
     (capture/evidence/experiment/salvage/partners/send_batch/deploy_prod/
     billing_enable/launch/gate_decision) — always via `Ledger.append`, atomic.
  5. **regenerate projections** — the S13 pure functions are re-derived on read
     (nothing cached; INV-COND-3's "no durable in-memory state").
- **Errors (fail closed):** an unauthorized/denied action → `CommandRefused` carrying
  the OWNER's reason (Gov's denial text / S5's typed guard error — never a
  conductor-authored rule); unknown command → `CommandRefused` (RED + denied);
  malformed args → `CommandRefused` naming the field. **No partial effect:** refusal
  before the act leaves the ledger untouched; the acting subsystem's own atomicity
  covers the act itself (INV-COND-3).
- **Side effects:** exactly the owning subsystem's appends + the conductor's one
  recorder fact where the table says so. **Determinism:** deterministic given the
  ledger + injected clock (workflow commands are the S10 LLM path). **Auth class:**
  per the frozen S6 matrix — never decided here.

### The call-through table (owner per command — INV-COND-1)
| Command | Owner → act | Event appended (by) |
|---|---|---|
| `capture` | recorder | `capture` (+`to_state: CAPTURED`) (conductor) |
| `frame` | S5 `transition(v, FRAMED, payload)` | `frame` (S5) |
| `admit` | S5 `transition(v, VALIDATING, token)` | `admit` (S5) |
| `validate.evidence` | recorder | `evidence_gate` (conductor) |
| `validate.experiment` | recorder (`channel` → live; `metric` → result) | `experiment_live` / `experiment_result` (conductor) |
| `spend.envelope` | S6 `envelope_open(vid, cap)` | `spend_envelope` (S6) |
| `spend.meter` | S6 `spend(vid, amount)` | `spend_meter`/`spend_breach` (S6) |
| `send.stage` | S6 `authorize` (budget, two-key on scale) | `send_batch` + token id (conductor) |
| `gate` | S13 brief (critic required) → S5 `transition`/`grant_omw` | S5's event + `gate_decision` (conductor) |
| `advance.express` | S5 `transition(express=True)` | `transition` (S5) |
| `shape` / `build` | S10 `Workflow.run(state row)` | `artifact_produced` (S10 checkpoint) |
| `recruit.partners` | recorder | `partners` (conductor) |
| `deploy.prod` / `billing.enable` | S6 `authorize` (two-key RED) | `deploy_prod`/`billing_enable` + token id (conductor); **no real effect exists in v1 — the authorization boundary is the end of the line (INV-TEST-SAFE)** |
| `launch` | S6 `authorize` (RED) | `launch{kit_ref}` + token id (conductor) |
| `pivot` | S5 `pivot(v, …, token)` | `pivot_fork`+`kill`+`capture` (S5) |
| `graduate` | S5 `transition(v, GRADUATED, token)` | `graduate` (S5) |
| `kill` | S5 `transition(v, KILLED, token, reason)` | `kill` (S5) |
| `salvage` | recorder (≥1 asset type — R-SALVAGE-TYPES shape check) | `salvage` (conductor) |
| `consolidate` | S9 `Memory.consolidate()` | `consolidate` (S9) |
| `calibrate` | S13 `calibration()` (pure read) | none |
| `pause` / `resume` | S5 `pause/resume(reason)` | `pause`/`resume` (S5) |
| `pipeline` / `brief` / `killday` / `gatebrief` | S13 pure reads | none |

### `Conductor.gate_brief(venture_id: str) -> GateBrief`
- Delegates to S13 `Projections.gate_brief` (docs/40 §8) — the fixed schema with the
  **mandatory Critic field** (INV-COND-2): assembly FAILS CLOSED (`NoCriticForGate`)
  when no critic take exists on the venture's record (no `artifact_produced` with a
  `critic_tier` and no prior `gate_decision`) — no gate is presentable without one.
- The `gate` command consumes this brief: its `gate_decision` payload carries
  `{brief_ref, recommendation, decision, critic_tier}` (docs/41 §2).

### `Conductor.workflows` (wiring data — the REAL state→workflow table)
- S12 owns the docs/13 rows the A8 registry validates: CAPTURED→scout,
  VALIDATING→analyst, SHAPING→builder, BUILDING→builder, LAUNCHED→growth — each
  checkpointing the **additive** `artifact_produced{artifact_ref, capability,
  critic_tier}` event (docs/41 §2 additive evolution, updated in the same PR per
  docs/62).

## Public value types
`CommandResult{ok, command, color, venture_id, event_id?, data?, reason}` ·
errors `ConductorError` / `CommandRefused` (carries the owner's reason) /
`NoCriticForGate` (INV-COND-2). Owner errors (S5's typed guard errors, S6's denial
Decisions, S7's `CheckpointError`) surface unchanged — one refusal vocabulary per rule.

## Consumed surface
Config (routes/budgets/memory), Ledger+Registry (IF-1), Lifecycle (IF-4:
`can_transition/transition/slots/clock/pivot/grant_omw/pause/resume`), Gov (IF-3:
`classify/authorize/envelope_open/spend/send_budget_remaining/record_override`),
Security (IF-3, via the S10 CHECKPOINT path), Router (IF-2, behind S10), Memory
(`retrieve/write_lesson/consolidate` behind S10/S9), Workflow (IF-5: `run`) — all live.

## Interface stability
- **Frozen (docs/40 §8):** `Conductor.command(name, args, token?) -> CommandResult` +
  `Conductor.gate_brief(v) -> GateBrief` + the command-name vocabulary (S6 matrix) +
  INV-COND-1..3 semantics. Breaking change = ICR (docs/43 §4).
- **Additive v1 notes (docs/43 §7):** the `artifact_produced` event type (IF-1
  additive); per-command `data` payload enrichment; future scheduler-driven workflow
  commands for the remaining states.
- **Internal/free to change:** handler decomposition, the recorder-fact payload
  builders, the wiring constructor.

### Founder CLI (`conductor/cli.py`) — additive, no surface change
A thin terminal shell over `Conductor.command` + the S13 projections for driving the
by-hand daily + kill-day loop (docs/05). It adds NO rule and NO durable state
(INV-COND-1/3): `build_factory` is the composition root wiring the fully live stack;
`main` translates one CLI subcommand → one `command(name, args, token)` call, prints,
and exits (a fresh process per invocation over the same ledger). RED commands halt
without `--approve` (the owner's refusal, exit 1); `--approve` mints the single-use
grant at the Gov boundary (`gov.grant`, scope == the owner's action name) and passes
it through — minted and consumed inside the one process. v1 command set: capture,
frame, admit, validate-evidence, validate-experiment, gate, kill, salvage,
pause/resume, pipeline, brief, killday, gatebrief. Two fail-closed seams stand in for
ops-phase wiring: `NoTransport` (every model transport) and `NoEmbedder` (the local
embedder) — neither is on any v1 command path. Nothing here is a frozen surface.

### Real model transport (`conductor/transport.py`) — additive, wiring-layer
The ops-phase HTTP client the Router's adapters wrap (router IMPLEMENTATION §6.1: composed
at wiring, never inside S8). `HttpOpenAITransport` (Groq/OpenRouter/local Ollama, OpenAI
`/chat/completions`) and `HttpGeminiTransport` (the Gemini shim's native `generateContent`);
`build_transports(config, key_lookup)` composes `{provider_id: transport}` from Config
(base_url/key_env NAMES only) + the injected `key_lookup` (A1's `env.env_key_lookup`) for
secrets. Keys are read by name at call time, placed only in the auth header, and NEVER
logged or put in an exception/event. Cloud PII enforcement stays in the adapter `_guard`
(runs before `complete`) — a `contains_pii` context never reaches the transport. The real
local embedder is A7's `OllamaEmbedder`, wired via the existing `build_factory(embedder=)`
seam. `build_transports(..., send=)` is an injectable HTTP-sender seam (tests pass a fake;
the smoke's `--debug` passes a logging wrapper that surfaces the endpoint URL, model id, and
HTTP status/body per attempt with the key redacted). Model ids in `config/` are each
provider's REAL API model string (e.g. Groq `llama-3.3-70b-versatile`), sent verbatim to the
provider. Nothing here is a frozen surface.
