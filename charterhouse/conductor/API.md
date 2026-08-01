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

### The idea note (`conductor/notes.py`) — additive, 2026-08-01
`capture --note/--note-file` stores the founder's own words about a venture and `advise`
threads them into the PRODUCE prompt as their own `IDEA (founder's words):` section — before
this, `note_ref` was an opaque label nothing ever opened, so the only per-venture text a
capability saw was the **codename** and it invented the rest.

Two placements are deliberate. **The text goes to the vault, never the ledger payload**
(`<vault>/ventures/<vid>/note.md`); the event keeps `note_ref` + a `contains_pii` boolean, so
the audit trail stays small and free text never meets the S4 payload backstop. The write goes
through S7 `checkpoint` (redact → independent scan → fail closed), so the copy the model reads
carries redaction tokens and the raw original stays in the local-only `.private.md` sidecar;
a residual finding refuses the capture outright (INV-PII-2 — nothing written, nothing
recorded). **The note reaches the runner as DATA**, read here and passed to
`Workflow.run(note=…)`, because PREPARE/PRODUCE/CRITIQUE have no vault path reachable from
their frames — keeping beat isolation structural rather than teaching a beat to open files.

`contains_pii` is the SCANNER's verdict OR the founder's `--pii` flag: the human may always
over-classify, never under-classify, and **the tag does not depend on them remembering it** —
`advise` reads it back from the capture event, so a PII-bearing idea degrades to local routing
with no flag at the advise call. `recorded_note` folds the ledger for a fact the Conductor
itself recorded (the same shape as `_gate` calling `gate_brief`), not a rule re-implemented
here (INV-COND-1). Requires the additive `security`/`vault_dir` seams on `Conductor`; without
them `capture --note` refuses rather than storing unscanned text. A `note_ref` that resolves
to no file means "no note" — every pre-existing ledger carries the old `note-<vid>` label, so
that is the normal case on existing history, never an error.

### `advise` — the AI verdict command (additive, 2026-07-31)
Runs the venture's **CURRENT-state** workflow (PRODUCE→CRITIQUE) via S10 and records the
critic take, so a gate becomes presentable (INV-COND-2). State-driven, not hardcoded: a
VALIDATING venture gets `analyst`, per the docs/13 table; a state with no row surfaces S10's
`UnknownWorkflow` unchanged (fail closed). **YELLOW, not RED** (S6 matrix, additive name):
it meters model spend like `build`, but it is an AI opinion, never a founder decision — it
moves no venture (the CHECKPOINT event is state-neutral by construction) and crosses no gate,
so the RED set (`admit`/`gate`/`kill` = the founder's levers) is unchanged and `--approve`
still means exactly those three. `args["contains_pii"]` maps to a `Require(contains_pii=True)`
that applies to **both** LLM beats — produce and critique alike degrade to local (INV-PII-3).
The recorded `artifact_produced` payload carries `critic_verdict`/`critic_model`/`steer`
(docs/41 §2 additive), which is how the Gate Brief replays a STEER with its provenance.

**Producer routes are per-row** (`STATE_ROLE`): the judgment rows whose artifact goes to a
founder gate (CAPTURED, VALIDATING) produce on `reasoning`; the making rows stay on `draft`.
Per-row rather than a global flip, so `shape`/`build` keep the route they merged with.

### Live boot (`build_factory(..., live=True)`) — additive
The production path (`__main__`) now wires the REAL transports (`build_transports`) and the
local `OllamaEmbedder`, which is what lets `advise` call a model at all. The default stays
fail-closed (`NoTransport`/`NoEmbedder`) so no test reaches the network by omission
(INV-TEST-SAFE); only the `__main__` boot opts in. The factory clock is now seeded via
`clock_from_ledger` (S5), so accumulated active time and the paused flag survive the process.

### Real model transport (`conductor/transport.py`) — additive, wiring-layer
The ops-phase HTTP client the Router's adapters wrap (router IMPLEMENTATION §6.1: composed
at wiring, never inside S8). `HttpOpenAITransport` (Groq/OpenRouter + any OpenAI-shaped local
server, OpenAI `/chat/completions`), `HttpOllamaTransport` (the local Ollama chat path on
Ollama's **native** `/api/chat`) and `HttpGeminiTransport` (the Gemini shim's native
`generateContent`);
`build_transports(config, key_lookup)` composes `{provider_id: transport}` from Config
(base_url/key_env NAMES only) + the injected `key_lookup` (A1's `env.env_key_lookup`) for
secrets. Keys are read by name at call time, placed only in the auth header, and NEVER
logged or put in an exception/event. Cloud PII enforcement stays in the adapter `_guard`
(runs before `complete`) — a `contains_pii` context never reaches the transport. The real
local embedder is A7's `OllamaEmbedder`, wired via the existing `build_factory(embedder=)`
seam. `build_transports(..., send=)` is an injectable HTTP-sender seam (tests pass a fake;
the smoke's `--debug` passes a logging wrapper that surfaces the endpoint URL, model id, and
HTTP status/body per attempt with the key redacted). Model ids in `config/` are each
provider's REAL API model string (Groq `llama-3.3-70b-versatile`, Ollama `llama3.1:8b`,
Gemini `gemini-2.0-flash`), sent verbatim to the provider. Every request carries an explicit
`User-Agent: charterhouse/1.0` (urllib's default UA is edge-blocked by some providers).

**Free profile: zero Gemini dependency (2026-07-30).** The live smoke confirmed Groq
reasoning 200 OK, the local embed OK, and the PII cloud-block holding — but Gemini returns 429
with `limit: 0` (its free tier is provisioned at zero for this account, so it will never
answer). The `free` profile therefore routes no live role through Gemini: the **critic is local
`qwen3:8b`** (family `qwen` — cross-family against the Groq `llama` producer, so INV-WF-2 tier
1 still holds) with a local `llama3.1:8b` fallback (same family as the producer → tier 2 if
qwen3 fails, never a lost critic), and `reasoning`'s dead Gemini fallback hop is removed —
Groq is the only free provider serving the route's 32k `min_ctx`, so exhaustion + pause is the
honest behaviour rather than burning an attempt on a guaranteed 429. Every critic candidate is
local, so critiques never leave the machine. The gemini model/provider/transport stay in the
catalog for other profiles and for model portability. **Remaining limit:** the `web` role still
resolves to Gemini — `gemini-2.0-flash` is the only catalog model with web capability, so this
needs a web-capable provider, not a reroute; nothing in v1 calls role `web`.

**VRAM discipline (local Ollama).** The local chat path uses Ollama's native `/api/chat`
rather than its OpenAI-compatible endpoint, because `keep_alive` is not an accepted field
there — it would be silently dropped and the model would hold VRAM for the default 5 minutes
after every call. Each local request therefore carries `keep_alive: 0` (`stream: false`,
`max_tokens` → `options.num_predict`), so Ollama unloads the model as soon as the response
completes and **zero VRAM is held while the factory is idle**; the trade is a reload from disk
per local call. `keep_alive` is Ollama-only and never appears in a cloud body (asserted).
`build_transports` keys this on the provider id `ollama`, not on `kind == "local"` — a local
LM Studio / vLLM server still gets the OpenAI-compat transport. A7's `OllamaEmbedder` sends
the same `keep_alive: 0` on `/api/embeddings` (the other resident local model).
Nothing here is a frozen surface.
