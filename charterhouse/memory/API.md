# Memory (S9) — API
Owner: A7 Memory Agent   ·   Matches docs/40 §6 exactly (frozen seam)   ·   This doc freezes the **Memory surface** (docs/12 "interface frozen early so the Framework (S10) can stub retrieval"); built against live IF-1 (Ledger), IF-2 COMPLETE (Config/Router), IF-3 (Security)

## Exposed surface

### `Memory.retrieve(task: TaskContext, k: int) -> WorkingSet`
- **Preconditions:** `task` is the query context `{text, tags, venture_id?, segment?,
  active_time}`; `k >= 0` (`k` bounds the *retrieved* records; Doctrine is not counted
  against it).
- **Postconditions:** returns `WorkingSet{doctrine, records, k}` where `doctrine` is the
  vault Doctrine text **always included** (INV-MEM-1; empty string in the legitimate
  pre-doctrine factory state — never an error) and `records` are **at most `k`**
  `ScoredLesson`s drawn ONLY from `status == "active"` rows — retired/superseded are
  excluded *before* ranking, and the full store is **never** returned regardless of `k`
  (INV-MEM-1). Ranking is the docs/33 weighted score
  `w1·semantic + w2·tag_match + w3·recency + w4·confidence (+ w5·segment_match when the
  task carries a segment)`, weights from the injected `RetrievalWeights` (docs/33
  "tunable via config" — see IMPLEMENTATION §6.1). Each `ScoredLesson` carries its
  `score` **and the per-component breakdown** (auditability: the gate brief can show *why*
  a lesson surfaced). Deterministic total order: score desc, then `lesson_id` asc —
  identical inputs always return the identical WorkingSet.
- **Errors (fail closed):** store open/read failures propagate typed (`MemoryEngineError`
  subtypes); an embed-model pin violation discovered on read → `EmbedModelMismatch`
  (reused from S2 — one mismatch type across the seam). No partial WorkingSet.
- **Side effects:** none (read-only; no ledger append). **Determinism:** deterministic
  given the store + weights (the query embedding is the local deterministic embedder in
  tests; Ollama in production). **Auth class:** GREEN.

### `Memory.write_lesson(lesson: Lesson) -> lesson_id`
- **Preconditions:** `lesson.text` is **already-redacted** content (redaction happens
  upstream at CHECKPOINT, S7 — this API never redacts); `kind` ∈ the docs/33 vocabulary
  (`lesson|playbook|research_chunk|segment_insight`), `status` ∈
  (`active|retired|superseded`), `0.0 <= confidence <= 1.0`, non-empty `text`/`source_ref`.
- **Postconditions:** the text is **verified PII-free with the merged S7 `Scanner`
  BEFORE any embedding happens** (INV-MEM-4 — verification, not redaction; no drift with
  S7); on a clean scan the vector is computed **locally** via the injected `Embeddings`,
  the row (docs/33 schema, stamped with the pinned `embed_model`) is added to the store,
  and exactly one `lesson_written{lesson_id, tags, confidence}` event is appended
  (docs/41 §2). Returns the assigned `lesson_id`.
- **Errors (fail closed):** any scanner finding → `PIIEmbedBlocked` naming finding
  *kinds only* (never values) — **zero embedder calls, zero store writes, zero ledger
  appends**; invalid shape → `LessonInvalid`. Ledger append failure propagates (the row
  write is then rolled back — no orphan vectors).
- **Side effects:** one store row + one `lesson_written` append on success.
  **Determinism:** deterministic given the embedder. **Auth class:** GREEN.
- **Additive kwarg seam (docs/43 §7):** `scope: tuple[str, ...] | None = None` — when a
  caller capability supplies its declared memory scope (docs/54 §S11), a lesson whose
  tags fall outside it is refused (`ScopeViolation`). `None` (default) = trusted caller
  (Conductor path); S11 owns scope *declaration*, S9 only enforces the supplied tuple.

### `Memory.consolidate() -> ConsolidationReport`
- **Postconditions:** a deterministic pass over the **view** (INV-MEM-3): duplicate
  groups (same kind, cosine ≥ `dup_threshold`) are merged — highest-confidence member
  kept, others marked `superseded`; `active` lessons with
  `confidence < retire_below` are marked `retired`; a tag recurring across
  ≥ `promote_min_ventures` distinct ventures is **promoted** to one new `playbook` row
  (deterministic canonical assembly of the member texts — **no LLM**); doctrine
  candidates are returned as **proposals only** (the founder writes Doctrine, never this
  code). Appends exactly one `consolidate{merged, retired, promoted}` event. **The
  ledger is never edited** — all mutations are `status` flips / new rows in the vector
  view, and the pre-consolidation lesson set remains reconstructible from the ledger's
  `lesson_written` history (reversibility, INV-MEM-3).
- **Errors:** store/ledger failures propagate typed; the pass is all-or-nothing per
  group (a failed group aborts before its event).
- **Side effects:** view status flips, ≤1 playbook row per promoted tag, one
  `consolidate` append. **Determinism:** fully deterministic. **Auth class:** GREEN.

### `Memory.reindex(reason: str) -> None`
- **Preconditions:** `reason` is a non-empty explanation — reindex is **guarded**
  (INV-MEM-2): a blank reason → `UnguardedReindex`, nothing touched.
- **Postconditions:** every row's (already-redacted) text is re-embedded with the
  **current** injected embedder; the table is rewritten and the store pin **and** the
  `EMBED_MODEL` marker (the same marker A1's preflight checks, docs/25 §4) are updated to
  the current model. Re-running with the same embedder is byte-deterministic (same
  vectors). This is the ONLY path that changes the pin — a mismatch at open always
  raises, never silently rebuilds (INV-MEM-2).
- **Errors:** `UnguardedReindex`; embed/store failures abort with the original index
  intact (rebuild into a temp table, swap on success).
- **Side effects:** table rewrite + marker/pin update. **Auth class:** GREEN (local
  compute only).

### `Embeddings.embed(text: str) -> tuple[float, ...]`  (protocol) · `OllamaEmbedder`
- **LOCAL only** (docs/40 §6 "never PII to cloud" — locality by construction: the sole
  production implementation is `OllamaEmbedder(host, model, transport?)` against the
  loopback Ollama endpoint from `EnvContext`; **no cloud embedder class exists in S9**).
  `dim` property exposes the fixed vector dimension. The transport is injected (tests:
  A11's `FakeEmbedder` implements this protocol; the Ollama HTTP shape is unit-tested
  with a fake transport — no network anywhere, INV-TEST-SAFE).
- **Errors:** transport/shape failures raise `EmbedFailed` (fail closed; no retry loop —
  the caller decides).

### `MemoryStore` (internal wiring, free to change)
- LanceDB-backed row store on `vectors_dir` (from A1's `EnvContext` at wiring — S9 reads
  no env). `open()` initializes an empty store (writing the `EMBED_MODEL` marker) or
  verifies the recorded pin against the configured model — mismatch →
  `EmbedModelMismatch` (same check A1 makes at preflight; defense in depth).

## Public value types
`TaskContext{text, tags, venture_id?, segment?, active_time}` ·
`Lesson{lesson_id, kind, text, tags, venture_id?, segment?, confidence, status,
created_active_time, source_ref}` (docs/33 schema minus store-stamped fields) ·
`ScoredLesson{lesson, score, components: RankingComponents}` ·
`RankingComponents{semantic, tag_match, recency, confidence, segment_match}` ·
`WorkingSet{doctrine, records, k}` · `ConsolidationReport{merged, retired, promoted,
doctrine_proposals}` · `RetrievalWeights{w_semantic, w_tag, w_recency, w_confidence,
w_segment, half_life_active, dup_threshold, retire_below, promote_min_ventures, max_k}`
(`max_k` is the hard working-memory bound backing "never the full store" — `k` is
clamped to it) ·
errors `MemoryEngineError` / `LessonInvalid` / `PIIEmbedBlocked` / `UnguardedReindex` /
`ScopeViolation` / `EmbedFailed`; `EmbedModelMismatch` is **reused from S2**
(`charterhouse.env.types`) — one mismatch-refusal type across the seam (A6 precedent
with S7's `PIIRouteBlocked`).

## Consumed surface
- **Ledger (S4, IF-1, real):** `Ledger.append(Event)` for `lesson_written` /
  `consolidate` (docs/41 §2 payload shapes); failures propagate — never swallowed.
- **Security (S7, IF-3, real):** the merged `Scanner.scan(text) -> Findings` as the
  INV-MEM-4 verification layer (S9 re-implements NO S7 rule; finding *kinds* only ever
  appear in errors). Redaction itself stays upstream at CHECKPOINT.
- **Env (S2, real, at wiring):** `EnvContext.vectors_dir` / `.ollama_host` /
  `.embed_model` — supplied by the composition root; S9 itself never reads `os.environ`
  (A1's static env-boundary scan stays green).
- **Router (S8, IF-2):** none at runtime — embeddings are local-only and NOT routed
  through `LLMClient` (docs/22: the embed path is Ollama-direct; recorded here because
  IF-2 unlocked A7's build slot, docs/52).
- **A11 harness:** `FakeEmbedder` (frozen signature) is the test-time `Embeddings`.

## Interface stability
- **Frozen (docs/40 §6, this doc):** `Memory.retrieve/write_lesson/consolidate/reindex`
  signatures + `Embeddings.embed` + the `TaskContext`/`Lesson`/`WorkingSet`/
  `ConsolidationReport` shapes + INV-MEM-1..4 semantics. Breaking change = ICR
  (docs/43 §4).
- **Additive v1 notes (docs/43 §7):** `write_lesson(..., scope=)`; the
  `RetrievalWeights` injection seam; `ScoredLesson.components` (richer breakdown fields
  may be added).
- **Internal/free to change:** LanceDB table layout, exact-ranking implementation (ANN
  optimization later), consolidation grouping internals, marker file format, module
  layout.
