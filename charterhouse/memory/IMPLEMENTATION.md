# Memory (S9) — IMPLEMENTATION
Owner: A7 Memory Agent   Subsystem: S9   Source of truth: docs/12 (build contract) + docs/33 (store/embedding/retrieval, frozen) + docs/40 §6 (seam) + docs/41 §2 (events) + docs/54 §S9 / docs/55

## 1. Responsibility (one paragraph)
S9 owns the compounding knowledge substrate: local embedding of **already-redacted**
text, the LanceDB vector store on K:, top-K working-memory retrieval (Doctrine always),
and the consolidation/promotion/retirement pass — a **reversible view over the immutable
ledger**. It MUST NOT: redact (S7 owns redaction at CHECKPOINT — S9 only *verifies*
cleanliness), edit or rewrite ledger events (append-only, corrections are new events),
route through cloud models (embeddings are local by construction), decide lifecycle or
governance outcomes, read `os.environ` (A1's seam), or dump the full store into any
caller's hands via `retrieve` (top-K only).

## 2. Invariants enforced
- **INV-MEM-1** — "retrieval returns top-K only; Doctrine always included;
  retired/superseded excluded." Guaranteed in `retrieval.py`: candidates are filtered to
  `status == "active"` *before* ranking; the result is truncated to `k`; `WorkingSet`
  always carries the doctrine text (loaded per call from the vault path).
- **INV-MEM-2** — "embedding model id pinned in config; a change triggers a guarded full
  re-index, never silent." Guaranteed in `store.py`: the store records the pin (the
  `EMBED_MODEL` marker A1 preflight reads, + per-row `embed_model`); `open()` on a
  mismatch raises `EmbedModelMismatch` (reused S2 type); the ONLY pin-changing path is
  `Memory.reindex(reason)` which requires a non-empty reason (`UnguardedReindex`
  otherwise) and re-embeds everything.
- **INV-MEM-3** — "consolidation is a reversible view over the immutable ledger; the
  ledger is never edited." Guaranteed in `consolidate.py`: mutations are limited to
  vector-view `status` flips + new playbook rows + ONE appended `consolidate` event;
  no ledger-mutating API even exists on the store; reversibility is tested by rebuilding
  the lesson set from the ledger's `lesson_written` history and comparing.
- **INV-MEM-4** — "no PII embedded (redaction upstream at CHECKPOINT); embeddings
  computed locally." Guaranteed in `facade.py::write_lesson`: the merged S7 `Scanner`
  runs over `lesson.text` (and tags/source_ref) BEFORE any embed; any finding →
  `PIIEmbedBlocked` (kinds only), with **zero** embedder calls and zero writes. Locality:
  the only production embedder is `OllamaEmbedder` on the loopback host from
  `EnvContext`; no cloud embedding code exists in S9.

## 3. Internal design
Modules (all deterministic; **no LLM anywhere in S9** — the embedder is a local encoder,
not a generator):
- `types.py` — frozen dataclasses (`TaskContext`, `Lesson`, `ScoredLesson`,
  `RankingComponents`, `WorkingSet`, `ConsolidationReport`, `RetrievalWeights`) + the
  error taxonomy. `RetrievalWeights` carries the docs/33 ranking weights + consolidation
  thresholds as **frozen data with defaults** (§6.1).
- `embeddings.py` — `Embeddings` protocol (`embed(text) -> tuple[float, ...]`, `dim`);
  `OllamaEmbedder(host, model, transport=None)` posting to `/api/embeddings` via an
  injected transport callable (tests inject a fake; no `httpx`/network dependency in CI).
  The body carries `keep_alive: 0` (ops fix, 2026-07-30) so Ollama unloads the embed model
  the moment the response completes — zero idle VRAM, at a reload from disk per embed.
- `store.py` — `MemoryStore`: LanceDB (pinned `lancedb==0.34.0`) table `memory` under
  `vectors_dir`, rows per the docs/33 schema. `open()` init-or-verify (marker `EMBED_MODEL`
  — the same file A1 preflight checks, docs/25 §4); `add(row)`; `set_status(id, status)`;
  `active_rows()` / `all_rows()` (internal); `rebuild(rows, embed_model)` (temp-table swap
  used by reindex); `delete_row` does NOT exist (view flips only — INV-MEM-3).
- `retrieval.py` — pure ranking: cosine(unit vectors) → `semantic`; tag overlap ratio →
  `tag_match`; `0.5 ** (age_active / half_life_active)` → `recency` (factory
  **active-time**, never wall clock — deterministic); row confidence → `confidence`;
  segment equality → `segment_match` (weight applied only when the task has a segment).
  Exact scoring over active rows (portfolio scale; ANN later — RISKS R6), top-K with the
  deterministic tie-break (score desc, `lesson_id` asc).
- `consolidate.py` — duplicate grouping (same `kind`, cosine ≥ `dup_threshold`; keep
  highest confidence, tie → earliest id), retirement (`confidence < retire_below`),
  promotion (a tag spanning ≥ `promote_min_ventures` distinct ventures → one `playbook`
  row assembled deterministically: sorted member texts joined under a canonical header,
  confidence = mean, source_ref = member id list), doctrine **proposals** (returned, never
  written).
- `facade.py` — `Memory(store, embedder, ledger, scanner, doctrine_path, weights, actor="system")`:
  wires the surface, owns the INV-MEM-4 verification, appends `lesson_written` /
  `consolidate` events (docs/41 §2 payloads), loads doctrine (`vault/memory/DOCTRINE.md`
  by default; missing file → `""`, §6.2).
**Durable state:** the LanceDB table + `EMBED_MODEL` marker under `vectors_dir` — a
**rebuildable projection** ("High" backup tier, docs/33): the source of truth for lessons
remains the ledger (`lesson_written`) + vault records.

## 4. Dependencies
- **S4 Ledger (IF-1, real):** `Ledger.append(Event) -> event_id`; `Event` envelope from
  `charterhouse.contracts.events` (payloads: `lesson_written{lesson_id, tags, confidence}`,
  `consolidate{merged, retired, promoted}`).
- **S7 Security (IF-3, real):** `Scanner(known_identities).scan(text) -> Findings`
  (deterministic, no LLM). S9 consumes the class directly (A11 precedent in
  `logging/types.py`) so the bar never drifts from S7's.
- **S2 Env (real, at wiring):** `EnvContext{vectors_dir, ollama_host, embed_model}` from
  `preflight()` — supplied by the composition root; plus the reused `EmbedModelMismatch`.
- **A11 harness (S15, real):** `FakeEmbedder` (frozen: `embed(text)->tuple`, `dim`),
  `pii_corpus`, tmp-path real `Ledger`.
- **lancedb==0.34.0** (new pinned runtime dep; wheels verified on Python 3.14/win —
  RISKS R1).

## 5. Failure behavior
Every failure fails closed, typed, with **no partial effect**:
- PII finding at `write_lesson` → `PIIEmbedBlocked` (kinds only) — nothing embedded,
  stored, or appended.
- Invalid lesson shape → `LessonInvalid` (named field) — nothing touched.
- Pin mismatch at `open`/read → `EmbedModelMismatch` — store unusable until a guarded
  reindex (mirrors A1's boot refusal).
- `reindex("")` → `UnguardedReindex`; a mid-reindex failure leaves the original table
  intact (temp-table swap).
- Ledger append failure in `write_lesson` → propagate + roll back the just-added row
  (no vector without its ledger event).
- Embedder transport failure → `EmbedFailed`; no retry loop, no fallback-to-cloud
  (there is no cloud path).
- Out-of-scope write (when `scope` supplied) → `ScopeViolation`.
No "guess/continue" path exists; `retrieve` never returns a partial WorkingSet.

## 6. Open questions → RESOLVED
1. **Where do the "tunable via config" ranking weights live?** The frozen Config surface
   (docs/40 §1) had no memory accessor at A7 time; the interim answer was injection with
   code defaults. **RESOLVED (final, 2026-07-19, feat/a2-accessors):** the additive
   `Config.memory` accessor landed — routes.yaml's committed `memory:` block (docs/33
   values, strict-key validated) flows through `RetrievalWeights.from_config` at wiring.
   The injection seam is unchanged (no frozen surface touched); RISKS R9 retired.
2. **Doctrine source & the empty-doctrine state.** RESOLVED: doctrine text is read from
   an injected `doctrine_path` (default `vault/memory/DOCTRINE.md`, docs/23 vault map);
   a missing/empty file is the legitimate pre-doctrine factory state → doctrine `""`,
   still always present in the WorkingSet (INV-MEM-1 is "always included", not
   "always non-empty"). Never an error.
3. **Embed-model mismatch ownership vs A1.** A1 preflight refuses to *boot* on a marker
   mismatch (merged, config/IMPLEMENTATION §6 boundary note). RESOLVED: S9's store makes
   the **same check at open** with the **same reused type** (defense in depth — memory can
   be constructed in tests/tools without preflight), and S9 owns the only legal pin-change
   path (guarded `reindex`). The marker file A1 reads is the marker S9 writes — one
   artifact, no drift.
4. **How is "no PII embedded" enforced without redacting here?** RESOLVED: verification,
   not redaction — the merged S7 `Scanner` gates every text entering the embedder;
   findings refuse with kinds only. Redaction remains upstream at CHECKPOINT (S7);
   S9 re-implements no S7 rule.
5. **Promotion/doctrine without an LLM.** RESOLVED: promotion is deterministic assembly
   (recurring-tag rule + canonical text join); doctrine changes are **proposals in the
   report** — the founder writes Doctrine. LLM-assisted summarization, if ever wanted, is
   a later capability (S11) calling `write_lesson`, not S9 logic.
6. **`write_lesson` "scoped by caller capability" (docs/40 §6).** S11 owns scope
   *declarations* (docs/54 §S11). RESOLVED: additive `scope` kwarg — S9 enforces the
   supplied tuple (tags ⊆ scope) and refuses otherwise; `None` = trusted Conductor path.
7. **Embeddings via Router?** docs/12 lists "Embeddings/Router (S8)" as consumed.
   RESOLVED: embeddings do NOT go through `LLMClient` (docs/22/docs/33: Ollama-direct,
   local-only; A6 IMPLEMENTATION §6 explicitly deferred embeddings to A7 as local-only).
   S8's unlock was scheduling (IF-2 completeness), not a runtime call.
