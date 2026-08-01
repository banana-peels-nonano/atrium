# FOUNDER QUICKSTART — driving Charter House for the first time

**Audience:** the founder, at a terminal, with one real idea. **Owner:** Program.
**What this is:** the exact commands, in order, to take one venture from Capture to a
verdict — with a worked example you can copy-paste, where the approvals happen, and where
the receipts come out. §7 lists honestly what does not work yet.

Two facts that make this safe to experiment with:

- **Only one command calls a model.** `advise` (step 9) runs the AI producer + critic and
  needs your Groq key in `.env` plus Ollama running. Everything else is offline bookkeeping.
- **Nothing is hidden state.** Each command is one fresh process that reads the ledger,
  does one thing, appends one fact, and exits. Stop anywhere and resume later.

---

## 1. Setup (once per terminal)

```powershell
function ch { uv run python -m charterhouse.conductor.cli --repo K:\the_charter_house --data-dir K:\Data\charter_house --profile free @args }
```

Every command below is then `ch <something>`. To rehearse first, point `--data-dir` at a
scratch folder instead — delete the folder afterwards and nothing is lost.

Reading the output: each line starts `OK <command> [COLOR] event=<id>`. The colour is the
action's risk class — **GREEN** just records a fact, **YELLOW** spends something metered,
**RED** needs your explicit approval (§3). `event=` is the receipt id for that fact.
Exit codes: `0` did it, `1` refused (nothing moved), `2` bad invocation.

## 2. The loop, in order

The worked example runs one venture — id `demo-001`, codename `atrium-demo` — from idea to
verdict. Substitute your own id and codename; keep the id stable, it's the handle for
everything after.

| # | Command | What it does / what you'll see |
|---|---|---|
| 1 | `ch capture --venture demo-001 --codename atrium-demo --source inbox --note-ref note-demo-001` | **Capture.** Records the idea's birth; the venture now exists at `CAPTURED`. Prints your first `event=` id. |
| 2 | `ch pipeline` | The board — every venture, state, score. Your at-a-glance "where is everything". |
| 3 | `ch frame --venture demo-001 --brief-ref brief:demo-001 --score 19 --quotes 2` | **Frame.** Attaches your score and how many primary quotes back it. Moves `CAPTURED → FRAMED`. Score ≥18 is admit-worthy, <14 is kill-worthy; ≥2 quotes required. |
| 4 | `ch admit --venture demo-001` | **Deliberately fails** — admission is RED. Prints `REFUSED … RED action requires a founder token`, exit 1, venture unmoved. Run it once to see the halt. |
| 5 | `ch admit --venture demo-001 --approve` | **Admit (the gut-yes lever).** `--approve` mints and spends the token (§3). Moves `FRAMED → VALIDATING` and takes one of the 3 validating slots. |
| 6 | `ch validate-evidence --venture demo-001 --verdict PASS --quote-count 7 --segment-kind smb-ops` | Records the evidence sub-gate — `PASS` or `FAIL`, with the quote count and which segment they came from. |
| 7 | `ch validate-experiment --venture demo-001 --channel cold-email` | Marks the experiment **live** on a channel. |
| 8 | `ch validate-experiment --venture demo-001 --metric reply_rate --actual 0.4 --threshold 5.0 --verdict FAIL` | Records the **result**: the metric, what you got, what you needed, the verdict. This is the fact the recommendation folds from. |
| 9 | `ch advise --venture demo-001` | **The AI verdict.** Runs the venture's workflow for its current state (VALIDATING → the *analyst* capability): a producer drafts the analysis on Groq, then a **different-family** critic (local `qwen3:8b`) attacks it and proposes a direction. Records the artifact + critic take on the ledger. Prints the tier, the verdict, and the **steer**. Add `--pii` if the venture's context contains personal data — that confines **both** model calls to local models. |
| 10 | `ch gatebrief --venture demo-001` | The fixed verdict packet: recommendation, **steer**, critic tier, the evidence it rests on, and the artifact. Refuses until step 9 has run (INV-COND-2 — no gate without a critic take). |
| 11 | `ch killday` | Your daily read: every active venture briefed, **worst-first (KILL → HOLD → ADVANCE)** with its steer and evidence. Anything with no critic take yet is **named, never dropped**, with the `advise` command to fix it. |
| 12 | **Your call — steer:** `ch gate --venture demo-001 --decision ADVANCE --to SHAPING --approve` | **The steer lever.** Takes the brief's direction and moves the venture on (`VALIDATING → SHAPING`). RED: needs `--approve`. Use `--decision OMW` to grant one more week instead. |
| 12b | **Your call — kill:** `ch kill --venture demo-001 --reason "reply rate 0.4% vs 5% threshold" --approve` | **The kill lever.** Moves `VALIDATING → KILLED`, your reason on the permanent record. Run it without `--approve` first to see the halt. |
| 13 | `ch salvage --venture demo-001 --asset-type audience_list --asset-type anti_pattern` | After a kill: banks what it leaves behind. Refuses if you name nothing — `anti_pattern` is a first-class asset, the lesson is the point. |
| 14 | `ch pipeline` | Confirms the end state. |

**The AI judges; you decide.** `advise` produces an opinion and records it — it moves nothing.
Only step 12 changes a venture's state, and only with your `--approve`.

`ch brief` gives the triaged daily read and `ch pause` / `ch resume` freeze the clock — read
§7.2 and §7.3 before relying on either.

## 3. RED actions and how the approval token works

Three commands are RED — `admit`, `gate`, `kill`. Note what is **not** on that list:
`advise` is YELLOW. The AI can spend model tokens to form an opinion without asking you,
because an opinion moves nothing; only your three levers change a venture's state. They are the decisions that cost slots,
kill work, or move a venture at a gate, so they refuse to run on your say-so alone:

```
REFUSED admit: gate transition refused by Governance: RED action requires a founder token;
none presented (INV-GOV-1)
```

**`--approve` IS the authorization act.** You never create, copy, or store a token yourself.
When you pass `--approve`, the CLI asks Governance to mint a single-use grant scoped to
exactly that action and that venture (a 15-minute TTL), hands it to the owning subsystem,
and that subsystem spends it exactly once. Minted and consumed inside the one process — no
token file, nothing to leak or reuse. Omitting `--approve` is always safe: the command halts
and the venture does not move.

The token id lands in the receipt (`authorization` in the ledger line), so every RED action
is permanently traceable to an approval you gave.

## 4. Where the verdict and the receipts come out

Everything lands in `<data-dir>\ledger\segment-00001.jsonl` — one JSON line per fact, in
order, each carrying `prev_hash`: a SHA-256 chain, so any later edit to history is
detectable. Read it back:

```powershell
Get-Content K:\Data\charter_house\ledger\segment-00001.jsonl | ForEach-Object {
  $e = $_ | ConvertFrom-Json; "{0,-18} to={1,-11} {2}" -f $e.type, $e.to_state, $e.authorization }
```

**Your refusals are receipts too.** Every halt (steps 4 and 11) is recorded as an `error`
event in the same chain — the trail shows what you were stopped from doing, not only what
you did.

## 5. What a real run looked like

Verbatim, from a throwaway ledger on 2026-07-30 (abridged to the interesting lines). This
predates the `advise` command, so it ends in a kill; steps 9-12 above are the added path and
their shapes are shown in §5b.

```
$ ch capture --venture demo-001 --codename atrium-demo --source inbox --note-ref note-demo-001
OK capture  [GREEN]  event=01KYSFDEZNV2XNCF32TM9MDSJ5

$ ch frame --venture demo-001 --brief-ref brief:demo-001 --score 19 --quotes 2
OK frame  [GREEN]  event=01KYSFDKP2TDEPT78F9M1Z8B6G
  Result(ok=True, …, from_state=CAPTURED, to_state=FRAMED)

$ ch admit --venture demo-001
REFUSED admit: gate transition refused by Governance: RED action requires a founder token;
none presented (INV-GOV-1)                                                        (exit 1)

$ ch admit --venture demo-001 --approve
OK admit  [RED]  event=01KYSFEMSSYRN5SXZKAV5JR1TQ
  Result(ok=True, …, from_state=FRAMED, to_state=VALIDATING)

$ ch gatebrief --venture demo-001
REFUSED gatebrief: no critic take on record for venture 'demo-001' — no gate is
presentable without one (INV-COND-2)                                              (exit 1)

$ ch brief
OK brief  [GREEN]
  silence — nothing needs you today (INV-TRIAGE; a valid answer)

$ ch killday
OK killday  [GREEN]
  demo-001  — unbriefable (no critic take yet; named, never dropped)

$ ch kill --venture demo-001 --reason "reply rate 0.4% vs 5% threshold" --approve
OK kill  [RED]  event=01KYSFG73VF2XEHC20TV8D13XT
  Result(ok=True, …, from_state=VALIDATING, to_state=KILLED)

$ ch salvage --venture demo-001 --asset-type audience_list --asset-type anti_pattern
OK salvage  [GREEN]  event=01KYSFGPDAE88QCXX0FYMFGWP7

$ ch pipeline
OK pipeline  [GREEN]
  demo-001  atrium-demo  KILLED  score=19  [experiment_clock]
```

The resulting chain — the complete audit trail of that venture's life:

```
capture            to=CAPTURED    -              prev=000000000000
frame              to=FRAMED      -              prev=e858bbcf9113
error              to=-           -              prev=8aef1da1b097   <- the refused admit
admit              to=VALIDATING  tok=tok-443d   prev=43bb21c8afda
evidence_gate      to=-           -              prev=186e423d35e7
experiment_live    to=-           -              prev=b63a16b856fd
experiment_result  to=-           -              prev=07a5e5c90185
error              to=-           -              prev=949ee9eb9d2b   <- the refused kill
kill               to=KILLED      tok=tok-a27c   prev=71721a7f5146
salvage            to=-           -              prev=c8bbc60cbce3
```

## 5b. What the AI verdict prints

The shapes below are what the renderers emit (the wording is fixed; the model's own text is
whatever your idea earns). Not a transcript of a real idea — you run that one.

```
$ ch advise --venture demo-001
OK advise  [YELLOW]  event=<id>
  produced: ventures/demo-001/analyst-validating.md  (capability analyst, model llama-3.3-70b-versatile)
  critic tier 1 via qwen3:8b — verdict review
  steer: <the critic's concrete what-to-build-instead, on one line>
  gate brief is now presentable: charterhouse gatebrief --venture demo-001

$ ch gatebrief --venture demo-001
OK gatebrief  [GREEN]
  venture: demo-001  (atrium-demo)  state=VALIDATING
  score=19  active_in_state=0
  recommendation: KILL
  critic tier: 1  artifact=ventures/demo-001/analyst-validating.md
  steer: <direction>
  evidence: evidence:PASS(7 quotes), experiment:reply_rate:FAIL
```

`recommendation` is the mechanical fold of your recorded evidence; `steer` is the critic's
direction; `evidence` is what both rest on. The decision is still yours.

## 6. The state path

`CAPTURED → FRAMED → VALIDATING → SHAPING → BUILDING → LAUNCHED → EARNING → GRADUATED`, with
`KILLED → ARCHIVED` reachable from most points. Steps 1-14 cover `CAPTURED` through the
`VALIDATING` verdict and out the other side — kill, or steer on to `SHAPING`. From `SHAPING`
onward the same rhythm repeats: `ch advise` for the AI take on the current state, then
`ch gate --approve` for yours.

## 7. How the AI verdict works (and its limits)

### 7.1 Who judges what

`advise` runs two model calls behind one command:

1. **Producer** — the venture's capability for its current state (VALIDATING → *analyst*)
   drafts the analysis, on the `reasoning` route (Groq `llama-3.3-70b-versatile`).
2. **Critic** — a **different model family** attacks that draft (local `qwen3:8b`, family
   `qwen` vs the producer's `llama`). Cross-family is the point: a model is a poor judge of
   its own output, so the framework records *which tier* actually answered:
   - **tier 1** — different family critiqued it (what you want),
   - **tier 2** — same family, different model (the router had no cross-family option),
   - **tier 3** — the deterministic checklist floor (no model answered, or it would have
     been self-critique). **Tier 3 never produces a steer** — it gives mechanical findings.

The brief always shows the tier next to the steer, so you can tell real advice from a floor.
A steer is never invented: if the critic doesn't give one, the brief says so.

### 7.2 PII stays local, on both legs

`ch advise --venture <id> --pii` tags the run, and the router then confines **both** the
producer and the critic to local models. The critic leg matters as much as the producer: the
artifact text is what gets critiqued, so a cloud critic would be an egress too. With the tag
set, zero cloud sends happen on either leg — that's an enforced invariant (INV-PII-3), tested
by counting sends on every cloud transport, not a policy note.

### 7.3 What still doesn't work

- **GRADUATE** has no CLI subcommand; it stays on the `Conductor.command` API.
- **`brief` still under-reports.** It skips ventures that aren't gate-presentable, so it can
  print `silence` while something waits. **`killday` is the honest daily read** — it names
  unbriefable ventures and tells you the `advise` command to fix each one.
- **Active time accumulates but does not advance on its own.** The clock now survives across
  commands — the paused flag and accumulated active time are rebuilt from the ledger at every
  boot, so `pause`/`resume` works and the counter no longer resets to zero. But nothing yet
  *advances* it as real days pass: that needs elapsed wall-time recorded per event and folded
  against paused spans. Until then the active-day guards (SHAPING ≤10, BUILDING >15, the
  60-day evidence TTL) still won't fire on their own. Legality rules are all live; the
  time-based ones remain the open piece.
