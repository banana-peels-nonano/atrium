# Project meta-ledger

Charter House's own append-only, hash-chained audit trail — the project dogfooding its
own guarantee. Distinct from the **runtime venture ledger** (`data/ledger/`, which is
gitignored/local): this one is **committed**, and holds facts about Charter House as a
company/thesis, not about ventures inside the factory.

Every entry is appended through the real `charterhouse.ledger.Ledger.append` — so it
passes the structural PII/secret pre-check (INV: provable PII non-egress) and links the
tamper-evident SHA-256 chain (INV: immutable audit trail). `segment-00001.jsonl` is
canonical JSONL; the genesis event (`prev_hash` = 64 zeros) is the founding
enterprise-thesis kill-gate (2026-07-27). Corrections are new compensating events,
never edits.
