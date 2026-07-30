# FOUNDER QUICKSTART — driving Charter House for the first time

**Audience:** the founder, at a terminal, with one real idea. **Owner:** Program.
**What this is:** the exact commands, in order, to take one venture from Capture to a
verdict — with a worked example you can copy-paste, where the approvals happen, and where
the receipts come out. §7 lists honestly what does not work yet.

Two facts that make this safe to experiment with:

- **You need no API keys and no models.** Nothing in this command set calls a model or
  embeds anything — the whole loop runs offline.
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
| 9 | `ch gatebrief --venture demo-001` | The fixed verdict packet for one venture. **Refuses today** — §7.1. |
| 10 | `ch killday` | Every active venture, briefed, with a mechanical recommendation. Anything not yet briefable is **named, never dropped**. Use this as your daily read (§7.2). |
| 11 | `ch kill --venture demo-001 --reason "reply rate 0.4% vs 5% threshold"` | Deliberately fails — kill is RED. Same halt as step 4. |
| 12 | `ch kill --venture demo-001 --reason "reply rate 0.4% vs 5% threshold" --approve` | **The verdict.** Moves `VALIDATING → KILLED`, your reason on the permanent record. |
| 13 | `ch salvage --venture demo-001 --asset-type audience_list --asset-type anti_pattern` | Banks what the dead venture leaves behind. Refuses if you name nothing — `anti_pattern` is a first-class asset, the lesson is the point. |
| 14 | `ch pipeline` | Confirms the end state: `demo-001 atrium-demo KILLED score=19`. |

`ch brief` gives the triaged daily read and `ch pause` / `ch resume` freeze the clock — read
§7.2 and §7.3 before relying on either.

## 3. RED actions and how the approval token works

Three commands are RED — `admit`, `gate`, `kill`. They are the decisions that cost slots,
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

Verbatim, from a throwaway ledger on 2026-07-30 (abridged to the interesting lines):

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

## 6. The state path

`CAPTURED → FRAMED → VALIDATING → SHAPING → BUILDING → LAUNCHED → EARNING → GRADUATED`, with
`KILLED → ARCHIVED` reachable from most points. Steps 1-14 above cover `CAPTURED` through the
`VALIDATING` verdict — the part the CLI drives today. Everything past `VALIDATING → SHAPING`
needs the gate lever in §7.1.

## 7. What does NOT work yet (read before relying on the loop)

### 7.1 You can KILL from the CLI, but you cannot yet STEER

`gate` and `gatebrief` assemble the fixed Gate Brief, and that schema **cannot exist without
a Critic take** (INV-COND-2, by construction — a gate with no independent critique is not
presentable). A critic take comes from an `artifact_produced` event, which only a **workflow
run** creates, and the CLI exposes no workflow command. So today:

- **KILL** — works, via `ch kill --approve` (step 12). It transitions directly and needs no brief.
- **ADVANCE / OMW (steer)** — **blocked.** `ch gate --decision ADVANCE --to SHAPING --approve`
  refuses with `NoCriticForGate` even with `--approve`. Verified. This is the invariant doing
  its job, not a bug: no verdict without a critic take.
- **GRADUATE** — no CLI subcommand; it stays on the `Conductor.command` API.

What unblocks it: wire the (now working) model transports into `build_factory` — it already
takes a `transports=` seam, the CLI just defaults to the fail-closed `NoTransport` — and
expose the shape/build workflow commands. An ops-phase task, not a config change.

### 7.2 Use `killday`, not `brief`, as your daily read

`brief` silently skips any venture that isn't gate-presentable. In the run above it printed
`silence — nothing needs you today` while a venture with a **failed experiment** sat waiting
for a verdict. Until §7.1 lands, `silence` is not evidence that nothing needs you.
`killday` is the honest surface: it names unbriefable ventures instead of skipping them.

### 7.3 The clock does not survive the process — deadlines are inert, `resume` is broken

Each invocation builds a fresh in-memory factory clock starting at zero, and nothing seeds it
from the ledger. Two observed consequences:

**Deadline guards never fire.** Every event stamps `active_time: 0`, so the active-day rules
— SHAPING ≤10 days, the BUILDING >15-day kill guard, the 60-day evidence TTL — never trip.
The state machine's *legality* rules are all live and enforced; only the *time-based* ones are
dormant. Don't expect the factory to tell you a venture has gone stale.

**`pause` / `resume` don't work across commands.** `pause` pauses the clock inside one
process, which then exits; the next process starts unpaused, so `resume` always refuses:

```
$ ch pause --reason "holiday"
OK pause  [GREEN]  event=01KYSFP6F03BDFKADMKVSGJAD2
$ ch resume --reason "back"
REFUSED resume: factory is not paused                                             (exit 1)
```

Both need the same fix: reconstruct the clock (accumulated active time + paused flag) from
the ledger's `pause`/`resume`/`experiment_live` events at boot, the way every other piece of
state is already derived. The events are all recorded correctly — nothing is lost, and the
fix is purely additive at the composition root.
