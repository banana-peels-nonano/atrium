# Memory (S9) — TESTPLAN
Owner: A7 Memory Agent   (written BEFORE implementation)

Conventions per the merged suites: **real LanceDB store on tmp_path**, real tmp-path
Ledger (A3 convention), the merged S7 `Scanner` (no fake security), A11's `FakeEmbedder`
as the injected `Embeddings` (**no network anywhere** — INV-TEST-SAFE), typed fail-closed
errors via `pytest.raises`, INV mapping in docstrings, seeded `parametrize` property
tests vs an independent oracle. Support in `tests/unit/_a7_support.py`.

## Unit tests (`tests/unit/test_memory.py`)
| Test | Asserts | Fake(s) | Covers |
|---|---|---|---|
| `test_retrieve_topk_only_never_full_store` | 25 active lessons, `k=5` → exactly 5 records; `k=0` → 0 records; an absurd `k=1000` is clamped to `weights.max_k` — no `k` ever yields the full store | FakeEmbedder, real store | **INV-MEM-1** |
| `test_retrieve_doctrine_always_included` | doctrine text present in every WorkingSet — with hits, with an empty store, and with `k=0` | FakeEmbedder | **INV-MEM-1** |
| `test_retrieve_missing_doctrine_is_empty_not_error` | no `DOCTRINE.md` → `doctrine == ""`, retrieval still works (pre-doctrine state, IMPLEMENTATION §6.2) | FakeEmbedder | INV-MEM-1 edge |
| `test_retrieve_excludes_retired_and_superseded` | the semantically-closest lesson marked `retired` (and another `superseded`) never appears, even at large `k`; the next-best active one does | FakeEmbedder | **INV-MEM-1** |
| `test_ranking_matches_independent_oracle_property` (property, `seed` in `range(20)`) | seeded corpora: result order == an oracle recomputation of `w1·sem + w2·tag + w3·rec + w4·conf (+ w5·seg)` written independently in the test | FakeEmbedder | **INV-MEM-1** ranking (property) |
| `test_ranking_component_semantics` | tag overlap boosts rank; older `created_active_time` decays via the half-life; higher confidence wins ties; `segment_match` applies only when the task has a segment; `ScoredLesson.components` exposes each term | FakeEmbedder | ranking components |
| `test_ranking_deterministic_tiebreak` | equal-score records order by `lesson_id` asc; identical call → identical WorkingSet | FakeEmbedder | determinism |
| `test_write_lesson_roundtrip_retrievable` | `write_lesson` → `retrieve` returns it; row carries the docs/33 schema incl. `embed_model` pin; returns the `lesson_id` | FakeEmbedder, real Ledger | embed→store→retrieve (docs/54 §S9) |
| `test_write_lesson_appends_lesson_written_event` | exactly one `lesson_written{lesson_id, tags, confidence}` event per write | real Ledger | docs/41 §2 |
| `test_write_lesson_assigns_id_when_blank` | a blank `lesson_id` gets a store-assigned, letters-only id (returned + on the row — RISKS R7) | FakeEmbedder | write path |
| `test_write_lesson_invalid_shapes_refused` | bad kind / status / confidence out of [0,1] / empty text / empty source_ref → `LessonInvalid`, store+ledger untouched | — | fail closed |
| `test_write_lesson_pii_blocked_before_embed` (parametrized over `pii_corpus.POSITIVES`) | every corpus positive → `PIIEmbedBlocked`; **embedder spy called 0 times**; store row count unchanged; **no ledger append**; message names the finding *kind*, never the value | embedder spy, merged S7 Scanner | **INV-MEM-4** |
| `test_write_lesson_clean_text_accepted` (parametrized over `pii_corpus.NEGATIVES`) | every corpus negative embeds + stores fine (precision guard — memory must not dead-lock on ordinary factory content) | FakeEmbedder, Scanner | INV-MEM-4 complement |
| `test_write_lesson_scope_seam` | `scope=("pricing",)` accepts a pricing-tagged lesson, refuses a channel-tagged one (`ScopeViolation`); `scope=None` accepts both | FakeEmbedder | additive seam (docs/54 §S11 boundary) |
| `test_write_lesson_rollback_on_append_failure` | a ledger whose `append` fails → the error propagates AND the just-written row is rolled back (store count unchanged; no orphan vector) | failing-ledger double | RISKS R10 |
| `test_store_records_pin_and_marker` | a fresh store writes the `EMBED_MODEL` marker (the file A1 preflight reads) + per-row `embed_model` == configured model | FakeEmbedder | **INV-MEM-2** |
| `test_open_with_changed_model_refused` | reopen with a different model id → `EmbedModelMismatch` (reused S2 type); store not silently rebuilt; rows untouched | FakeEmbedder ×2 dims | **INV-MEM-2** |
| `test_reindex_requires_reason` | `reindex("")`/whitespace → `UnguardedReindex`; nothing changed | — | **INV-MEM-2** guard |
| `test_reindex_updates_pin_and_reembeds` | after a guarded `reindex(reason)` with a new embedder: marker + every row's `embed_model` updated; vectors recomputed; reopen with the new model succeeds, with the old one refuses | FakeEmbedder (two "models") | **INV-MEM-2** |
| `test_reindex_deterministic` | reindex twice with the same embedder → byte-identical vectors + row set (docs/54 §S9 "reindex determinism") | FakeEmbedder | **INV-MEM-2** |
| `test_consolidate_merges_duplicates` | near-identical lessons (same kind) → highest-confidence kept `active`, others `superseded`; report lists the merge pairs | FakeEmbedder | **INV-MEM-3** |
| `test_consolidate_retires_low_confidence` | `confidence < retire_below` → `retired`; ≥ threshold stays `active` | FakeEmbedder | **INV-MEM-3** |
| `test_consolidate_promotes_recurring_to_playbook` | a tag across ≥ `promote_min_ventures` distinct ventures → exactly one new `playbook` row (deterministic assembly, no LLM); doctrine proposals returned, **nothing written to doctrine** | FakeEmbedder | **INV-MEM-3** promotion |
| `test_consolidate_never_edits_ledger` | ledger events before the pass are **byte-identical** after it; event count grows by exactly one (`consolidate{merged, retired, promoted}`) | real Ledger | **INV-MEM-3** |
| `test_consolidate_reversible_from_ledger` | rebuilding the lesson set from the ledger's `lesson_written` history reproduces every pre-consolidation lesson (the view is a projection; the truth survives) | real Ledger | **INV-MEM-3** reversibility |
| `test_ollama_embedder_local_shape` | `OllamaEmbedder` posts `{model, prompt}` to the injected transport (loopback host), returns the embedding tuple; transport error → `EmbedFailed`; **no cloud embedder exists in S9** (module-surface assertion) | fake transport | **INV-MEM-4** locality |

## Integration tests (`tests/integration/test_memory_stack.py`)
| Test | Partner | Scenario | Expected |
|---|---|---|---|
| `test_it_checkpoint_to_memory_pii_flow` | S7 (real `Security.checkpoint`) + real Ledger + real store | raw text with corpus PII → CHECKPOINT redacts → the **clean** output is written as a lesson; the **raw** text attempted directly is refused | redacted lesson embedded + retrievable; raw → `PIIEmbedBlocked`, zero embeds; end-to-end proof that redaction lives upstream and S9 verifies (**INV-MEM-4** joint S7, docs/54 §S9) |
| `test_it_kill_salvage_lesson_retrievable_at_next_gate` | S4 (real Ledger events `kill`/`salvage`/`lesson_written`) | a venture dies → salvage assets → `write_lesson` (anti-pattern, venture-tagged) → a *different* venture's task retrieves at its next gate | the lesson surfaces in that WorkingSet's top-K (docs/54 §S9 acceptance loop) |

## Invariant coverage table
| INV / MUST | Test name | Tier |
|---|---|---|
| INV-MEM-1 top-K only / Doctrine always / retired excluded | `test_retrieve_topk_only_never_full_store`, `test_retrieve_doctrine_always_included`, `test_retrieve_excludes_retired_and_superseded`, ranking property | unit |
| INV-MEM-2 pinned model / guarded reindex, never silent | `test_store_records_pin_and_marker`, `test_open_with_changed_model_refused`, `test_reindex_requires_reason`, `test_reindex_updates_pin_and_reembeds`, `test_reindex_deterministic` | unit |
| INV-MEM-3 reversible view / ledger never edited | `test_consolidate_*` (5 tests) | unit |
| INV-MEM-4 no PII embedded / local embeddings | `test_write_lesson_pii_blocked_before_embed`, `test_write_lesson_clean_text_accepted`, `test_ollama_embedder_local_shape`, `test_it_checkpoint_to_memory_pii_flow` | unit + integration |
| docs/54 §S9 round trip + kill→salvage→lesson loop | `test_write_lesson_roundtrip_retrievable`, `test_it_kill_salvage_lesson_retrievable_at_next_gate` | unit + integration |
| docs/41 §2 event payloads | `test_write_lesson_appends_lesson_written_event`, `test_consolidate_never_edits_ledger` | unit |
| INV-DET (no env read; no LLM; import DAG) | A1's static env-boundary test (already sweeps `charterhouse/`) + no-cloud-embedder surface assertion | static |

## Fixtures/fakes needed (A11 shared harness + existing suites)
- **`FakeEmbedder`** (`tests.fakes.embedder`, frozen signature) — the injected
  `Embeddings` everywhere; two instances with different dims stand in for an
  embed-model change. A thin counting spy wraps it for the zero-calls assertions.
- **`pii_corpus`** (`tests.fixtures.pii_corpus`) POSITIVES/NEGATIVES + the merged S7
  `Scanner`/`Security` — the INV-MEM-4 bar.
- **tmp-path real `Ledger`** (A3 convention) for event assertions; tmp-path
  **real LanceDB store** (embedded lib, no server — INV-TEST-SAFE holds).
- No Clock needed: recency uses `TaskContext.active_time` vs `created_active_time`
  directly (pure data).

## Out of scope (test-safety, INV-TEST-SAFE)
No network socket anywhere: the Ollama embedder is exercised only through an injected
fake transport; LanceDB is embedded (files on tmp_path, no server, no Docker). No real
spend/send/deploy/charge exists in S9. Live Ollama smoke (real `nomic-embed-text`) is
optional and non-gating (docs/55 §7). Performance benchmarks (retrieval latency, embed
throughput) are the nightly tier (docs/55 §1), not this suite.
