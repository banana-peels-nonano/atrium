# 33 — VECTOR MEMORY (LanceDB schema + embedding + retrieval)
**Owner:** Memory Agent (A7) · **Subsystem:** S9 · **Source of truth:** Memory Architecture (frozen), Env Spec (Part 6)

## Store (frozen)
**LanceDB**, embedded, files on `K:\Data\charter_house\vectors\`. No server, no Docker. Rebuildable from the redacted lesson records (so "High" backup, not "Critical"), but snapshotted to avoid re-index cost.

## Embedding contract (frozen)
- Model: `nomic-embed-text` (local via Ollama). **Pinned** in config (`CHARTERHOUSE_EMBED_MODEL`).
- **Re-index rule (`INV-MEM-2`):** the index records the embedding model id it was built with. On mismatch, the system refuses to start and requires an explicit, guarded full re-index. Changing the embedding model is never silent (vectors from different models are incompatible).
- Only **redacted** text is embedded (`INV-MEM-4`/`INV-PII-1`); raw PII in `.private.md` is never embedded.

## Table schema (lessons + retrievable chunks)
```
id            : str (lesson id / chunk id)
vector        : float[]  (dim = model's; fixed per index)
kind          : "lesson" | "playbook" | "research_chunk" | "segment_insight"
text          : str (redacted)
tags          : str[]  (channel|pricing|segment|build|scoring…)
venture_id    : str | null
segment       : str | null
confidence    : float
status        : "active" | "retired" | "superseded"
created_active_time : int
source_ref    : str  (ledger/vault link; may point to a .private sidecar by ref, never inlining PII)
embed_model   : str  (pin; must equal config)
```

## Retrieval (`INV-MEM-1`)
- Working memory = **Doctrine (always)** + **top-K** retrieved records where `status == active`.
- Ranking score (weights in config, tunable): `w1·semantic + w2·tag_match + w3·recency + w4·confidence (+ w5·segment_match for cross-venture)`.
- Retired/superseded are excluded. The full store is never dumped into a prompt.

## Consolidation (`INV-MEM-3`)
- Merges duplicates, marks `retired`/`superseded`, promotes recurring lessons → playbooks (and proposes doctrine). This mutates the **vector/lesson view**, never the ledger. Fully reversible (the ledger replays the true history).
- Re-index on each consolidation pass; embedding model unchanged.

## Acceptance
`54` S9 + `55`: embed→store→retrieve round trip; ranking excludes retired; reindex determinism; embed-model-mismatch refused; no PII embedded (joint S7).
