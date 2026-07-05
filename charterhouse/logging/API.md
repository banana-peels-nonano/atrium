# Logging & Test Harness (S14 + S15) — API
Owner: A11 Test/Logging Agent   ·   Logging surface matches docs/40 §10

## Exposed surface — S14 Logging (`charterhouse/logging/`)

### `Log.event(level: Level, where: str, fields: Mapping) -> None`
- **Preconditions:** `fields` are structured (JSON-serializable). **Postconditions:** one structured line
  written to `K:\Logs\` (path from `EnvContext`); secret/PII-shaped fields are stripped/refused first.
- **Errors:** never raises on a normal log; a secret/PII field is dropped with a redacted marker (fail safe).
- **Side effects:** append to a log file. **Determinism:** deterministic. **Auth:** n/a. **Never logs secrets/PII (docs/24).**

### `Telemetry.record(llm_call_fields: Mapping) -> event_id`
- **Preconditions:** fields carry `{role, model, provider, tokens{in,out}, cost_usd, latency_ms, critic_tier?}` (docs/41 §2).
- **Postconditions:** appends an `llm_call` event via `Ledger.append`; returns its `event_id`. No secret/PII in payload.
- **Errors:** Ledger failure surfaced; the attempt is also operationally logged. **Determinism:** deterministic. **Auth:** n/a.

## Exposed surface — S15 Test harness (`tests/`, imported by all agents' tests)
```
FakeProvider(config)         # programmable latency/errors/rate-limits/canned outputs; stands in for Router LLM calls
FakeEmbedder(dim)            # deterministic fixed-dim vectors; stands in for local embeddings
InMemoryLedger()            # SAME signature as Ledger (docs/40 §2): append/read/replay/snapshot/restore
Clock(start, rate)           # injectable factory-active-time; supports pause/resume for TTL/deadline tests
pii_corpus()                 # fixture of names/emails/secrets/financials for scanner precision/recall
golden_set()                 # saved real tasks (5 scout briefs, 2 analyst packs, 1 builder task) for drift
Simulator(...)               # lifecycle driver; SHAPE frozen now, body lands with S4/S5/S10/S12
invariant_manifest()         # INV-* -> test-name map; CI reporter; unmapped MUST blocks phase-exit
```

## Consumed surface
- `Ledger.append` (A3, docs/40 §2) — telemetry sink. **Failure handling:** surface + operational-log the attempt.
- `EnvContext` (A1) — `logs_dir` resolution. As doubles, the harness *replaces* every subsystem interface in tests.

## Interface stability
- **Frozen:** `Log.event`, `Telemetry.record`, and each fake's **signature** (esp. `InMemoryLedger` == docs/40 §2).
  The `Simulator` and `invariant_manifest` shapes are frozen; their bodies fill in as dependencies land.
- **This is the harness half of the Wave-0 unlock** for A11-as-shadow (docs/52 §10 — A11 shadows the whole path).
  Recorded frozen in the Build Tracker **only on founder clearance**.
- Internal/free to change: log formatting, fake internals (as long as signatures + determinism hold).
