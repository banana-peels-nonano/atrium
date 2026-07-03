# 12 — MEMORY ENGINE (build contract)
**Owner:** Memory Agent (A7, co-owns store with A3) · **Subsystem:** S9 · **Source of truth:** Memory Architecture (frozen) · **Consumes:** Ledger (S4), Security (S7), Embeddings/Router (S8)

## Charter
The compounding knowledge substrate that improves with age. Compute embeddings locally, store vectors in LanceDB, retrieve top-K working memory, and consolidate/promote/retire lessons upward through the tiers — all without ever dumping the full store or leaking PII.

## Tiers (frozen)
Episodic Ledger (immutable) → Lessons (discrete records: tag, venture, evidence, confidence, status) → Playbooks → Doctrine. Working memory per task = Doctrine (always) + top-K retrieved.

## MUST
- `INV-MEM-1` retrieval returns top-K only; Doctrine always included; retired/superseded excluded.
- `INV-MEM-2` embedding model id pinned in config; a change triggers a guarded full re-index, never silent.
- `INV-MEM-3` consolidation is a reversible view over the immutable ledger; the ledger is never edited.
- `INV-MEM-4` no PII embedded (redaction happens upstream at CHECKPOINT, S7); embeddings computed locally.

## Retrieval ranking (frozen weights, tunable via config)
semantic similarity + tag match + recency + confidence (+ segment match for cross-venture). Details in `33`.

## Interfaces
- Exposes: `Memory.retrieve/write_lesson/consolidate/reindex`, `Embeddings.embed` (`40` §6).
- Consumes: `Ledger.read`, `Sec.tag`, local embedding endpoint.

## Deliverables
`memory/` (retrieval, consolidation, promotion, reindex). Store schema in `33`; lesson records in the vault.

## Acceptance / DoD
`54` S9 + `55`: embed→store→retrieve round trip; ranking excludes retired; reindex determinism; kill→salvage→lesson→retrievable-at-next-gate.

## Build order
Wave 3 (Phase 4). Depends on Ledger + Security + local embeddings. Interface frozen early so the Framework (S10) can stub retrieval.
