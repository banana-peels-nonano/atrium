# Charter House

**Owner:** Program · **Status:** built, tested, and archived as a learning artifact (see [Project status](#project-status--retrospective))

Charter House is a **governed, model-agnostic AI system that pressure-tests a startup idea
before anyone builds it.** You give it an idea in your own words; it runs a producer model
to draft the analysis, sends that draft to a **critic from a different model family** to
attack it, folds your recorded evidence into a mechanical recommendation, and hands you a
one-page verdict with a *steer* — what to build instead, or how to sharpen it. The AI
judges. You decide: every state change needs your explicit approval, and every fact —
including every refusal — lands on a hash-chained, append-only ledger.

The parts that make that trustworthy rather than merely convenient:

- **Provable PII non-egress.** Personal data is redacted, independently re-scanned, and
  fails closed; a venture tagged as PII-carrying confines *both* the producer and the
  critic legs to local models. Enforced in two layers (route filter + a guard inside every
  cloud adapter) and proven by tests that count sends on every cloud transport — zero.
- **An immutable audit trail.** One append-only JSONL ledger, SHA-256 `prev_hash` chain,
  replay-to-state. All boards, metrics, and briefs are pure projections; nothing is hidden
  state. Corrections are compensating events, never edits.
- **Human authorization at the boundary.** Actions are classed GREEN / YELLOW / RED.
  RED — admit, gate, kill — refuses to run without a single-use, scoped, 15-minute token
  minted at the moment you pass `--approve` and consumed exactly once by the owning
  subsystem.
- **Model portability.** Providers and models are config, not code. The same loop runs on
  Groq + local Ollama, cloud-only, or fully offline, by swapping a profile.

## Architecture in brief

Fifteen subsystems (S1 scaffold + S2–S15), one rule: **deterministic logic never calls a
model, and models hold no authority.**

| Layer | What it does |
|---|---|
| **Conductor** (S12) | The single chokepoint. Every command classifies → checks the owner's guards → acts → appends one fact → regenerates projections. Holds no rules of its own; a fresh process per invocation, the ledger its only memory. |
| **Lifecycle** (S5) | The state machine: `CAPTURED → FRAMED → VALIDATING → SHAPING → BUILDING → LAUNCHED → EARNING → GRADUATED`, with `KILLED → ARCHIVED`. WIP limits, transition guards, active-time clocks. Nothing else may move a venture. |
| **Ledger + Registry** (S4) | Append-only hash-chained event log; the registry is a replayed projection of it. State is *derived*, never stored twice. |
| **Governance + Security** (S6+S7) | Action classes and single-use tokens; redact → independent re-scan → fail closed, plus the `contains_pii` cloud-route guard. |
| **Router** (S8) | Role → model chains with constraint filtering, failover, budget tiers, and per-call cost telemetry. Real HTTP transports for Groq (OpenAI-compatible), Gemini (native shim), and local Ollama (native `/api/chat`, `keep_alive: 0` so a local model releases VRAM). |
| **Memory** (S9) | LanceDB-backed lessons + doctrine, weighted retrieval, deterministic consolidation. Nothing is embedded until it passes the PII gate. |
| **Capabilities** (S10+S11) | Six neutral `agents/*.agent.md` contracts — Scout, Analyst, Builder, Growth, Librarian, Critic — run by a five-beat workflow (PREPARE → PRODUCE → CRITIQUE → CHECKPOINT → GATE) whose model-facing beats are *structurally* unable to reach the vault or the ledger. The critic ladder records which tier actually answered: different family (1), same family (2), or a deterministic checklist floor (3). |
| **Projections** (S13) | Pure folds of the ledger: pipeline board, daily triage, kill-day list, gate brief. |
| **Config, Environment, Logging, Test harness** (S3, S2, S14, S15) | Schema-validated YAML config and profiles; a single env boundary (`preflight()` is the only env reader); structured logs and telemetry with redaction; shared fakes, property harness, and the invariant checker. |

Full specification: [`docs/`](docs/) — the Implementation Bible. Start at
[`docs/README.md`](docs/README.md) → [`docs/00_manifest.md`](docs/00_manifest.md).
The build's append-only history is [`docs/BUILD_TRACKER.md`](docs/BUILD_TRACKER.md).

## Running it

**[`docs/QUICKSTART.md`](docs/QUICKSTART.md) is the driver's manual** — the exact commands,
in order, from capture to verdict, with a worked example and where the approvals happen.

The short version — define the shell helper once, then three commands take an idea to a
verdict:

```powershell
uv sync --extra dev    # runtime deps + pytest (plain `uv sync` omits pytest)

function ch { uv run python -m charterhouse.conductor.cli --repo . --data-dir K:\Data\charter_house --profile free @args }

ch capture --venture idea-001 --codename "one-line name" --note "your idea, in full"
ch advise    --venture idea-001    # the only command that calls a model
ch gatebrief --venture idea-001    # the verdict packet: recommendation, steer, evidence
```

`--data-dir` is the ledger/vault home — point it at a scratch folder to rehearse and delete
the folder afterwards. Run the suite with `uv run pytest`, or the full ten-gate merge check
with `.\scripts\ci.ps1`.

Requires Python ≥ 3.13, `uv`, and `git`. Only `advise` calls a model — it needs a Groq key
in `.env` plus a local Ollama; everything else is offline bookkeeping. Copy
`.env.example` → `.env` for provider keys (`.env` is gitignored and blocked by the
secret-scan gate).

**Storage discipline:** nothing on C:. Tools → `K:\Tools`; caches →
`K:\Data\charter_house\cache`; model weights → `K:\Models`; venv → `.venv`. Set the
machine-level redirections from `.env.example` and verify before installing anything.

## Honest status

**What is real.** Every subsystem S2–S15 is built and merged on an always-green `main`.
All five interface freezes (IF-1..IF-5) plus the Memory surface are frozen *and* backed by
code. The full loop — capture → frame → admit → validate → advise → gate brief → steer or
kill → salvage — runs end-to-end through the single chokepoint over a live stack, with
real Groq + Ollama transports. All ten merge gates in `docs/63` are mechanically enforced
in CI (`scripts/ci.ps1`), not merely observed: tests, contract/ICR drift, lifecycle
invariants, anti-coupling imports, determinism imports, ownership, secret + PII scan.
**787 tests green on `main`**, verified by `scripts/ci.ps1` at the final merge. Nothing is
outstanding on a branch.

**What is not.** These are documented in [`docs/QUICKSTART.md`](docs/QUICKSTART.md) §7, not
papered over:

- **v1 has no real-world side effects by design.** Deploy, billing, and outbound send stop
  at the authorization boundary; the token-carrying events are recorded as the integration
  points a future ops layer would consume. Nothing has ever been deployed or sent.
- **The factory clock accumulates but does not advance on its own.** Pause/resume and
  accumulated active time survive across processes, but nothing folds real elapsed days
  yet, so the time-based guards (SHAPING ≤10 days, BUILDING >15, the 60-day evidence TTL)
  cannot fire unaided. All legality rules are live; the time-based ones are the open piece.
- `brief` under-reports (it skips ventures that aren't gate-presentable) — `killday` is the
  honest daily read. `GRADUATE` has no CLI subcommand; it stays on the `Conductor.command`
  API.
- The Gemini free tier used here is provisioned at `limit: 0` and permanently 429s, so the
  `free` profile routes around it entirely; Gemini remains in the catalog for portability.
  The `web` role is the last Gemini reference and nothing in v1 calls it.

## Project status / retrospective

Charter House was built to specification and it works — 750+ tests green behind ten
mechanical merge gates. The engineering discipline held: contracts before code, tests
before implementation, one owner per file, an append-only build ledger recording every
gate, every deviation, and every honest limit.

It was then pointed at its own premise. On 2026-07-27 the project's founding thesis was
recorded as the genesis event of a committed meta-ledger
([`docs/ledger/`](docs/ledger/README.md)) — appended through the real `Ledger.append`, so
the system's own guarantees vetted its own founding record — with a falsifiable prediction
and an explicit kill condition. Pressure-testing that thesis surfaced the finding that
matters more than the code:

**The idea-validator framing is a commodity.** "LLM reads your startup idea and critiques
it" is a weekend project with a hundred competitors, and no amount of engineering rigor
underneath changes what it is on the surface. **The asset is the governance and audit
substrate** — provable PII non-egress, an immutable hash-chained trail, human approval as a
structural boundary rather than a policy note, and model portability as a config change.
That substrate is domain-independent. It was built here to referee startup ideas; nothing
about it is specific to startup ideas.

The repository is **archived as a documented learning artifact**. It is not abandoned
mid-build and it is not seeking users: it is finished to its stated v1 boundary, green, and
left as a complete worked example of building an AI system where the model is the least
trusted component. The build tracker records how it was built; this section records what it
taught. Applying the verdict to itself was the system working, not the system failing.
