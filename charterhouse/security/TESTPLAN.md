# Security (S7) — TESTPLAN
Owner: A5 Governance/Security Agent   (written BEFORE implementation)

## Unit tests (`tests/unit/test_security.py`, support in `tests/unit/_a5_support.py`)
| Test | Asserts | Fake(s) | Covers |
|---|---|---|---|
| `test_scan_corpus_full_recall` | every planted positive in the PII corpus is detected with the right kind — **100% recall, any miss fails** | PII corpus | **`INV-PII-2`** (docs/54 §S7 corpus precision/recall) |
| `test_scan_negatives_no_false_positives` | the negatives set (clean prose, public pricing "$29/mo", ULIDs, content hashes, git SHAs) produces zero findings | PII corpus negatives | `INV-PII-2` precision |
| `test_scan_deterministic` | scanning the same text twice yields identical Findings (order, spans, kinds) — the pure-rules guarantee | PII corpus | **`INV-PII-2`** (no LLM in the path) |
| `test_redact_moves_pii_to_sidecar` | redacted text contains **no** corpus value; the sidecar `*.private.md` under the vault dir contains the raw values + token map; ref returned is a path, not content | tmp vault, corpus | **`INV-PII-1`** (R-REDACT) |
| `test_redact_tokens_stable` | the same raw value redacts to the same `⟨PII:kind:h8⟩` token across two documents/runs | tmp vault | `INV-PII-1` stable tokens |
| `test_redact_clean_text_untouched` | text with no PII returns `(text, None)`; no sidecar written | tmp vault | `INV-PII-1` |
| `test_vault_dir_validated_at_wiring` | constructing a `Redactor` with an impossible vault path raises at wiring — never at first redaction with raw PII in flight | tmp path blocker | RISKS R8 fail-closed wiring |
| `test_checkpoint_order_redact_then_scan` | `checkpoint` invokes redact before scan and scans the *redacted* output (recording spies); PII input passes checkpoint with a sidecar | spy redactor/scanner | **`INV-PII-1`** pipeline order |
| `test_checkpoint_fails_closed_on_residual` | fault injection (docs/24 acceptance): a misbehaving redactor that returns text unchanged → the independent scan catches it → `CheckpointError`; no clean text escapes; error names kinds, never values | MisbehavingRedactor, corpus | **`INV-PII-2`** fail-closed (R-PRECOMMIT-SCAN) |
| `test_tag_sets_contains_pii` | PII-bearing text → tagged; a context whose `sources` include a `.private.md` → tagged even when its text is clean; already-True never cleared; clean context stays untagged | tmp vault, corpus | **`INV-PII-3`** input |
| `test_cloud_adapter_blocks_pii` | a `FakeCloudAdapter` that consults the frozen guard refuses (`PIIRouteBlocked`) any `contains_pii` context and accepts a clean one — the S7 side of the joint S7×S8 test (to be re-run against the real Router at S8) | FakeCloudAdapter | **`INV-PII-3`** |
| `test_private_sidecar_gitignored` | the repo `.gitignore` contains the `*.private.md` rule, and a sample sidecar path is matched by it | repo file | **`INV-PII-4`** |
| `test_findings_never_carry_raw_pii` | for every corpus positive, `Finding.masked` does not contain the raw matched value (loggable findings) | corpus | **`INV-PII-4`** never logged |
| `test_scan_property_seeded` (property, `seed` in `range(20)`) | documents seeded-randomly composed from negatives with known positives planted at random offsets: the found set == the planted set (an independent oracle knows what was planted and where) | corpus, seeded composer | `INV-PII-2` (property) |

## Integration tests (`tests/integration/test_governance_security.py`)
| Test | Partner | Scenario | Expected ledger/state |
|---|---|---|---|
| `test_it_redacted_payload_accepted_raw_rejected` | S4 Ledger (real) | an event payload built from `checkpoint` output appends fine; the same payload with the raw corpus text is rejected by the Ledger's structural PII pre-check | S7 upstream + S4 backstop = defense in depth (docs/24) |

> The stress-test C3 arc (interview notes → embed → cloud retrieval) completes at S8/S9; its S7
> pieces — redaction of the notes, `contains_pii` tagging, cloud-guard refusal — are all covered
> above and noted for the joint test.

## Invariant coverage table
| INV / MUST | Test name | Tier |
|---|---|---|
| `INV-PII-1` redact+scan before embed/cloud; raw PII only in sidecar | `test_redact_moves_pii_to_sidecar`, `test_redact_tokens_stable`, `test_redact_clean_text_untouched`, `test_checkpoint_order_redact_then_scan` | unit |
| `INV-PII-2` deterministic scanner; CHECKPOINT fails closed on residual | `test_scan_corpus_full_recall`, `test_scan_negatives_no_false_positives`, `test_scan_deterministic`, `test_checkpoint_fails_closed_on_residual`, `test_scan_property_seeded` | unit |
| `INV-PII-3` `contains_pii` ⇒ cloud excluded | `test_tag_sets_contains_pii`, `test_cloud_adapter_blocks_pii` (joint with S8 later) | unit (joint at S8) |
| `INV-PII-4` `*.private.md` gitignored / never embedded / never logged / never pushed | `test_private_sidecar_gitignored`, `test_findings_never_carry_raw_pii`, `test_redact_moves_pii_to_sidecar` + CI gates 6/7 (secret + sidecar scan on every diff) | unit + CI |
| Fault injection: forced redaction miss → scan catches → fail closed (docs/24 acceptance) | `test_checkpoint_fails_closed_on_residual` | unit |
| `INV-DET` (no LLM anywhere in S7) | anti-coupling import check (A11 gate 5/10; hand-verified until active) | static |

## Fixtures/fakes needed (from A11 shared harness; A5-local until A11 lands)
- **PII corpus** (`tests/fixtures/pii_corpus.py`) — positives (names, emails, phones, SSN, cards,
  provider-key secrets, PEM block, high-entropy token, confidential financials) + negatives
  (clean prose, public pricing, ULID/hash/SHA strings). **Assembled at runtime** (concatenation)
  so no committed file ever trips the CI secret scan — the A3 precedent.
- **tmp-path vault dir** — sidecar target.
- **MisbehavingRedactor / spy scanner** (`_a5_support`) — fault injection + order recording.
- **FakeCloudAdapter** (`_a5_support`) — consults the frozen guard; stands in for S8 until the joint test.
- **Seeded document composer + planted-set oracle** (`_a5_support`) — the property test's independent truth.

## Out of scope (test-safety, INV-TEST-SAFE)
No network, no model call (local or cloud), no real embed, no push: the "cloud adapter" is a fake
that must *refuse*; sidecars are written only under `tmp_path`. Nothing in S7 can spend or send.
