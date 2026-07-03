# 40 — API CONTRACTS
## Every internal API surface, typed — the seams between subsystems
**Owner:** Interface Agent · **Source of truth:** Conductor Spec, Router, Memory, Governance, Lifecycle · **Status:** authoritative

> These signatures are **frozen interfaces**. Subsystems depend on these, not on each other's implementations (that is what enables parallel build, `52`). A breaking change requires a coordinated interface bump (`43`). Types are shown in Python-flavored pseudocode (implementation language per Env Spec); exactness of *shape* matters, not syntax.

## 1. Config (S3)
```
Config.get_route(role: str) -> Route            # {primary, fallback[], min_ctx?, needs_tools?, needs_web?}
Config.get_model(id: str) -> Model              # {provider, ctx, price_in, price_out, tier, good_at[]}
Config.get_provider(id: str) -> Provider        # {base_url, key_env, kind}
Config.profile -> str                           # active profile name
Config.budgets -> Budgets                        # {monthly_usd, on_exceeded, send_daily}
# INV-CFG enforced at load: every route model exists in models.
```

## 2. Ledger & Registry (S4)
```
Ledger.append(event: Event) -> event_id         # atomic, ordered, hash-chained
Ledger.read(filter: EventFilter) -> Iter[Event] # by venture/type/time
Ledger.replay(upto?: event_id) -> WorldState    # deterministic reconstruction
Registry.get(venture_id) -> Venture | None
Registry.query(state?: State) -> list[Venture]  # the portfolio-as-view
# Registry is a projection; INV-LEDGER: Registry == Ledger.replay()
```

## 3. Lifecycle (S5)
```
Lifecycle.can_transition(v: Venture, to: State) -> GuardResult  # {ok, reasons[], needs_auth: AuthClass}
Lifecycle.transition(v: Venture, to: State, token?: Token) -> Result
Lifecycle.slots() -> SlotState                  # current WIP counts vs limits
Lifecycle.clock(v) -> ActiveTime                # active-time; respects pause
# Emits transition/park/omw/pivot events via Ledger. No LLM. Fail closed.
```

## 4. Governance (S6) & Security (S7)
```
Gov.classify(action: Action) -> AuthClass       # GREEN | YELLOW | RED(+two_key?)
Gov.authorize(action: Action, token: Token) -> Decision  # ok | denied(reason)
Gov.envelope_open(v, cap_usd) -> Token          # RED
Gov.spend(v, amount) -> SpendResult             # YELLOW within cap; breach -> re-RED
Gov.send_budget_remaining(day) -> int           # founder-wide
Sec.redact(text) -> (clean: str, sidecar_ref: str)   # PII -> *.private.md
Sec.scan(text) -> Findings                       # deterministic; no LLM
Sec.tag(ctx: Context) -> Context                 # sets contains_pii
# INV-GOV-*, INV-PII-*. Deterministic. Fail closed.
```

## 5. Router (S8)
```
LLMClient.call(
  role: str,                     # NEVER a model id
  messages: list[Msg],
  tools: list[Tool] | None = None,
  require: Require | None = None # {min_ctx, needs_tools, needs_web, contains_pii}
) -> LLMResponse                 # {text, tool_calls[], model, usage, cost_usd, latency_ms, critic_tier?}
# Resolves role->model via Config; failover chain; degrade on budget.
# If require.contains_pii: cloud adapters are excluded (INV-PII-3, INV-ROUTE-3).
Adapter.complete(model, messages, tools, max_tokens) -> RawResult   # one per provider
```

## 6. Memory (S9)
```
Memory.retrieve(task: TaskContext, k: int) -> WorkingSet   # Doctrine + top-K; excludes retired
Memory.write_lesson(lesson: Lesson) -> lesson_id           # scoped by caller capability
Memory.consolidate() -> ConsolidationReport                 # reversible view; never edits ledger
Memory.reindex(reason) -> None                              # guarded; embedding model pinned
Embeddings.embed(text) -> vector                            # LOCAL only; never PII to cloud
# INV-MEM-*. Retrieval NEVER returns full store.
```

## 7. Capability Framework (S10)
```
Workflow.run(state: State, v: Venture) -> WorkflowResult
# Executes 5 beats: PREPARE(det) -> PRODUCE(cap) -> CRITIQUE(cap,diff-family) ->
#   CHECKPOINT(det: redact+scan+write+append) -> GATE(human).
# Only CHECKPOINT mutates state. PRODUCE/CRITIQUE idempotent+retryable.
Capability.produce(input: CapInput) -> Artifact              # no authority, no durable state
Critic.critique(artifact) -> Critique                        # different family; degrade ladder -> tier3 deterministic
```

## 8. Conductor (S12) — the command surface
```
Conductor.command(name, args, token?) -> CommandResult
# names: capture, frame, admit, validate.evidence, validate.experiment,
#   spend.envelope, spend.meter, send.stage, gate, advance.express, shape,
#   recruit.partners, build, deploy.prod, billing.enable, launch, pivot,
#   graduate, kill, salvage, consolidate, calibrate, pause, resume,
#   pipeline, brief, killday, gatebrief
# Each command: classify (Gov) -> enforce guards (Lifecycle/Gov/Sec) ->
#   (if authorized) act via owning subsystem -> append event -> regenerate projections.
# Conductor holds NO rule owned by S5/S6/S7 (INV-COND-1).
Conductor.gate_brief(v) -> GateBrief   # fixed schema; MUST include critic field (INV-COND-2)
```

## 9. Projections (S13) — all pure functions of the ledger
```
Projections.pipeline() -> Board
Projections.metrics() -> Metrics
Projections.daily_brief() -> DailyBrief
Projections.killday_brief() -> KillDayBrief
Projections.calibration() -> CalibrationReport
# Deterministic, regenerable; never a source of truth (INV-COND-3).
```

## 10. Logging (S14)
```
Log.event(level, where, fields)     # structured; NEVER secrets/PII
Telemetry.record(llm_call_fields)   # -> llm_call event
```

## Interface stability note
Signatures in §1–§10 are the frozen seams. During Phase build, an agent may stub a partner's interface from these contracts and proceed (parallelism). Any change to a signature here is a breaking change and follows `43` (coordinated bump + partner sign-off + version note).
