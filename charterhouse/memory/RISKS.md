# Memory (S9) — RISKS
Owner: A7 Memory Agent

## Risk register
| # | Risk | Likelihood | Impact | Category | Mitigation | Enforced |
|---|---|---|---|---|---|---|
| R1 | `lancedb` (first Rust-wheel runtime dep) breaks on a future Python/OS bump | low | high | refactor | pinned `lancedb==0.34.0` (wheel verified importable on Python 3.14/win before contracts were finalized); the store is isolated behind `MemoryStore` so a swap touches one module | code (`store.py` boundary) + `pyproject.toml` pin |
| R2 | PII reaches the vector store because a caller skipped CHECKPOINT | medium | critical | security | S9 never trusts the caller: the merged S7 `Scanner` gates every `write_lesson` before any embed (INV-MEM-4 verification layer); refusal names kinds only | code (`facade.py`) + tests (corpus-parametrized, zero-embed spy) |
| R3 | Scanner false positive dead-locks lesson writing on ordinary factory content | low | medium | ambiguity | the corpus NEGATIVES are an explicit acceptance test for S9's write path (precision guard, same bar as S7) | test (`test_write_lesson_clean_text_accepted`) |
| R4 | Silent embed-model drift corrupts retrieval (mixed-model vectors) | low | critical | architectural-integrity | pin recorded twice (marker + per-row); mismatch at open refuses (same reused S2 type A1's preflight raises); the only pin-change path demands a reason and re-embeds everything | code (`store.py`) + tests (INV-MEM-2 suite) |
| R5 | Consolidation quietly destroys history (a "merge" that loses a lesson) | low | critical | architectural-integrity | consolidation can only flip `status` / add rows — no delete API exists on the store; ledger untouched by construction; reversibility test rebuilds the set from `lesson_written` events | code (no-delete surface) + tests (byte-identical ledger, rebuild) |
| R6 | Exact (non-ANN) ranking gets slow as the store grows | medium | low | performance | acceptable at portfolio scale (thousands of rows); ranking is isolated in `retrieval.py` behind the frozen `retrieve` signature so an ANN prefilter (LanceDB native search) can land later without an ICR; nightly perf tier watches it (docs/55 §1) | doc (this row) + module boundary |
| R7 | ULID-style lesson ids in `lesson_written` payloads could trip S4's structural digit-run pre-check (flaky appends) | low | medium | ambiguity | lesson ids are generated with a non-digit-leading prefix and verified against the ledger's structural scan in the round-trip tests; if a collision class ever appears, ids switch to a letters-only alphabet (internal, not frozen) | test (round-trip through the real Ledger) |
| R8 | Doctrine file grows unbounded and bloats every WorkingSet | medium | low | performance | out of S9's authority (the founder writes Doctrine); surfaced as a size note in the retrieval path later; WorkingSet keeps doctrine separate from `records` so callers can budget | doc |
| R9 | Ranking weights drift from docs/33 intent because they live in code defaults, not config | medium | low | ambiguity | weights are one frozen typed value (`RetrievalWeights`) injected at wiring — a single obvious seam; cross-note to A2 for an additive `Config.memory` accessor (router-R9 pattern) | doc (IMPLEMENTATION §6.1) + code (injection seam) |
| R10 | Rollback gap: a store row is written but the `lesson_written` append fails | low | medium | architectural-integrity | `write_lesson` appends AFTER the row write and rolls the row back on append failure (delete-on-rollback is the one internal removal, before any reader can observe the row); tested via a failing-ledger double | code (`facade.py`) + test |

## Refactor-avoidance notes
- The frozen surface is exactly docs/40 §6 (4 methods + `Embeddings.embed`); everything
  heavy (LanceDB layout, ranking internals, consolidation grouping, marker format) is
  declared internal in API.md — later ANN/scale work is a no-ICR change.
- `EmbedModelMismatch` reused from S2 and the marker shared with A1's preflight: one
  artifact, one type — no dual-source drift to reconcile later.
- `RetrievalWeights` as a single injected value keeps the future `Config.memory`
  accessor a one-line wiring change (additive, docs/43 §7).
- The `scope` kwarg seam pre-wires S11's capability-scope enforcement without S9
  guessing S11's contract shape.

## Assumptions
- S7 `Scanner.scan` is deterministic, LLM-free, and its findings' `masked` values are
  loggable (security/API.md — matches).
- S4 `Ledger.append` is atomic and validates the envelope + structural PII pre-check
  (ledger/API.md — matches); `lesson_written`/`consolidate` are in the frozen
  `EventType` catalog (they are, contracts/events.py).
- A1's preflight owns the *boot-time* mismatch refusal and reads the `EMBED_MODEL`
  marker file (env/preflight.py — matches); S9 writing that marker at store init is the
  initialization preflight's Check 4 expects.
- A11's `FakeEmbedder` signature (`embed(text) -> tuple[float, ...]`, `dim`) is frozen
  (tests/fakes/embedder.py — matches).
- The vault layout (`vault/memory/`, `vault/lessons/`, `vault/playbooks/`) per docs/23
  exists in-repo (it does, gitkept).
