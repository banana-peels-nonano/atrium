"""The founder CLI — a thin terminal shell over ``Conductor.command`` + the S13
projections (conductor/API.md additive note; docs/05 daily + kill-day loop).

Deliberately minimal: it adds NO rule and NO state (INV-COND-1/3 — it builds the live
factory, dispatches ONE command, prints, exits; every invocation is a fresh process
over the same ledger, which INV-COND-3 makes correct by construction). RED actions
halt exactly as designed: without ``--approve`` the command runs tokenless and the
OWNER's refusal is printed (exit 1); ``--approve`` IS the founder authorization act —
it mints the single-use token at the Gov boundary (``gov.grant``) and passes it
through (minted AND consumed inside this one process, so token-store process-locality
is a non-issue). The v1 command set is the by-hand daily + kill-day loop (capture,
frame, admit, validate-evidence, validate-experiment, gate, kill, salvage,
pause/resume, pipeline, brief, killday, gatebrief); spend/send/deploy/billing/launch,
graduate/pivot and the shape/build workflow commands stay on the ``Conductor.command``
API until the ops phase wires real transports.

Boot note (honest): v1 takes ``--repo``/``--data-dir`` paths explicitly (no env read —
A1's boundary holds; the preflight-gated boot arrives with the ops phase). Two seams
fail closed like each other until then: the model path (``NoTransport`` — every
provider transport) and the embed path (``NoEmbedder`` — the local Ollama embedder),
each raising rather than reaching a network. The v1 command set never embeds or calls
a model, so neither stub is on any tested path; both carry the real pins so the store's
INV-MEM-2 marker is correct for the day ops wires the live ones.

Usage: python -m charterhouse.conductor.cli --data-dir K:\\Data\\charter_house <command> …
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from charterhouse.capabilities.framework import Workflow
from charterhouse.conductor import Conductor, build_registry
from charterhouse.conductor.transport import build_transports
from charterhouse.conductor.types import ConductorError
from charterhouse.config import Config
from charterhouse.env import env_key_lookup, load_env_file
from charterhouse.governance import Gov
from charterhouse.ledger import Ledger
from charterhouse.lifecycle import Lifecycle
from charterhouse.lifecycle.clock import clock_from_ledger
from charterhouse.memory import Memory, MemoryStore, OllamaEmbedder, RetrievalWeights
from charterhouse.capabilities.framework.types import WorkflowResult
from charterhouse.projections.types import (
    Board,
    DailyBrief,
    GateBrief,
    KillDayBrief,
    ProjectionsError,
)
from charterhouse.registry.facade import Registry
from charterhouse.router.facade import Router
from charterhouse.security import Scanner, Security

__all__ = ["NoEmbedder", "NoTransport", "build_factory", "main"]

# The RED commands this CLI can approve, mapped to their Gov token scopes. The scope
# MUST equal the owner's action name (S6 classify / S5 ``rule.auth_scope``) — for these
# three the CLI command name, the Gov scope, and the transition auth scope coincide.
APPROVE_SCOPES = {"admit": "admit", "gate": "gate", "kill": "kill"}
TOKEN_TTL_S = 900.0

# The local embedder's real pins (docs/33) — used by the live boot and carried by the stub
# so the store's INV-MEM-2 marker matches either way.
EMBED_MODEL = "nomic-embed-text"
EMBED_DIM = 768
DEFAULT_OLLAMA_HOST = "http://localhost:11434"


def _ollama_host() -> str:
    """The local embed endpoint, read by NAME through A1's env seam — never directly, so
    the environment boundary stays inside ``charterhouse/env/`` (docs/20)."""
    try:
        return env_key_lookup()("OLLAMA_HOST")
    except Exception:  # noqa: BLE001 — unset is normal; loopback is the documented default
        return DEFAULT_OLLAMA_HOST


class NoTransport:
    """The v1 model-path stub: every call fails closed so S8's failover exhausts into
    its designed ``ProvidersExhausted`` pause signal. Real transports = ops phase."""

    def complete(self, model, messages, tools=None, max_tokens=None):  # noqa: ANN001
        raise RuntimeError(
            f"{model}: no live model transport is wired (the ops phase opens on "
            "founder go-ahead) — failing closed")


class NoEmbedder:
    """The v1 embed-path stub (mirrors ``NoTransport``): a declared model/dim so the
    store pins correctly, but ``embed`` fails closed — no v1 command embeds. Real
    (local Ollama) embedder = ops phase."""

    def __init__(self, model: str = EMBED_MODEL, dim: int = EMBED_DIM) -> None:
        self._model = model
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, text: str):  # noqa: ANN001, ANN201
        raise RuntimeError(
            f"{self._model}: no live embedder is wired (the ops phase opens on "
            "founder go-ahead) — failing closed")


def build_factory(repo_root: str | Path, data_dir: str | Path,
                  vault_dir: str | Path | None = None, *, profile: str | None = None,
                  embedder=None, embed_model: str = EMBED_MODEL,  # noqa: ANN001
                  transports: dict | None = None, live: bool = False,
                  known_identities: tuple[str, ...] = ()):
    """Wire the fully live factory (the composition root): real Config over the
    committed ``config/``, real Ledger/Registry/Gov/Lifecycle/Security/Memory/
    Workflow/Conductor.

    ``embedder``/``transports`` are injection seams (tests pass fakes). ``live=True`` is
    the PRODUCTION boot: it wires the real HTTP transports and the local Ollama embedder,
    which is what makes ``advise`` able to call a model at all. The default stays
    **fail-closed** (``NoEmbedder``/``NoTransport``) precisely so no test can reach the
    network by omission (INV-TEST-SAFE) — only the ``__main__`` path opts in.
    """
    repo_root = Path(repo_root)
    data_dir = Path(data_dir)
    vault_dir = Path(vault_dir) if vault_dir is not None else data_dir / "vault"

    config = Config.load(repo_root / "config", profile)
    ledger = Ledger(data_dir / "ledger")
    registry = Registry(ledger)
    # The clock is DERIVED from the ledger like every other piece of state (INV-COND-3):
    # accumulated active time + the paused flag survive the process boundary, so active-day
    # guards accumulate and a `pause` is still in force for the next command.
    clock = clock_from_ledger(ledger)
    gov = Gov(ledger, config, clock=time.time)  # wall clock for token TTL + timestamps
    lifecycle = Lifecycle(ledger, registry, gov, clock)
    security = Security(vault_dir, known_identities=known_identities)

    if embedder is None:
        embedder = (OllamaEmbedder(_ollama_host(), embed_model, EMBED_DIM) if live
                    else NoEmbedder(embed_model))
    store = MemoryStore.open(data_dir / "vectors", embed_model, embedder.dim)
    memory = Memory(store, embedder, ledger, Scanner(known_identities),
                    vault_dir / "memory" / "DOCTRINE.md",
                    weights=RetrievalWeights.from_config(config.memory))

    if transports is None:
        if live:
            transports = build_transports(config, env_key_lookup())
        else:
            provider_ids = {config.get_model(mid).provider for mid in config.models()}
            transports = {pid: NoTransport() for pid in provider_ids}
    router = Router(config, ledger, transports=transports)

    workflow = Workflow(build_registry(repo_root / "agents"), router, memory, security,
                        ledger, vault_dir,
                        family_of=lambda mid: config.get_model(mid).family)
    conductor = Conductor(ledger=ledger, registry=registry, lifecycle=lifecycle,
                          gov=gov, memory=memory, workflow=workflow, clock=clock,
                          security=security, vault_dir=vault_dir)
    return SimpleNamespace(conductor=conductor, ledger=ledger, registry=registry,
                           lifecycle=lifecycle, gov=gov, security=security,
                           memory=memory, workflow=workflow, router=router,
                           config=config, clock=clock, vault_dir=vault_dir)


# --- argument surface (the thin translation to Conductor.command) -----------------------


def _build_parser() -> argparse.ArgumentParser:
    """One subparser per v1 command. Global path options are parsed only for the
    non-injected (``__main__``) boot; tests inject the factory and pass none."""
    p = argparse.ArgumentParser(prog="charterhouse", description=__doc__)
    p.add_argument("--repo", default=".", help="repo root (committed config/ + agents/)")
    p.add_argument("--data-dir", help="the ledger/vector home (required unless injected)")
    p.add_argument("--profile", help="config profile (e.g. free)")
    sub = p.add_subparsers(dest="command", required=True)

    def venture(sp):  # noqa: ANN001, ANN202
        sp.add_argument("--venture", required=True)
        return sp

    c = venture(sub.add_parser("capture", help="record a new venture (CAPTURED)"))
    c.add_argument("--codename")
    c.add_argument("--source")
    c.add_argument("--note-ref")
    c.add_argument("--note", help="your idea in your own words — stored in the vault and "
                                  "read by the capability at `advise` time")
    c.add_argument("--note-file", help="same, read from a file (markdown or plain text)")
    c.add_argument("--pii", action="store_true",
                   help="mark the idea text as carrying personal data: every later model "
                        "call for this venture stays local (the scanner also tags it "
                        "automatically if it recognises PII)")

    f = venture(sub.add_parser("frame", help="frame a captured venture (→FRAMED)"))
    f.add_argument("--brief-ref", required=True)
    f.add_argument("--score", type=int, required=True)
    f.add_argument("--quotes", type=int, required=True)

    a = venture(sub.add_parser("admit", help="admit to validation (RED — needs --approve)"))
    a.add_argument("--approve", action="store_true")

    ad = venture(sub.add_parser(
        "advise", help="run the venture's workflow (PRODUCE→CRITIQUE) and record a "
                       "critic take, so its gate becomes presentable"))
    ad.add_argument("--pii", action="store_true",
                    help="the venture's context carries PII: confine BOTH model calls to "
                         "local models (INV-PII-3)")

    ve = venture(sub.add_parser("validate-evidence", help="record an evidence gate"))
    ve.add_argument("--verdict", required=True)
    ve.add_argument("--quote-count", type=int)
    ve.add_argument("--segment-kind")

    vx = venture(sub.add_parser("validate-experiment", help="go-live or result"))
    vx.add_argument("--channel")
    vx.add_argument("--metric")
    vx.add_argument("--actual", type=float)
    vx.add_argument("--threshold", type=float)
    vx.add_argument("--verdict")

    g = venture(sub.add_parser("gate", help="a gate verdict (RED — needs --approve)"))
    g.add_argument("--decision", required=True, help="ADVANCE | KILL | OMW")
    g.add_argument("--to", help="target state for ADVANCE (e.g. SHAPING)")
    g.add_argument("--reason")
    g.add_argument("--spec-ref")
    g.add_argument("--fits-days", type=int)
    g.add_argument("--approve", action="store_true")

    k = venture(sub.add_parser("kill", help="kill a venture (RED — needs --approve)"))
    k.add_argument("--reason", required=True)
    k.add_argument("--approve", action="store_true")

    s = venture(sub.add_parser("salvage", help="bank salvaged assets (names required)"))
    s.add_argument("--asset-type", action="append", help="repeatable; anti_pattern is first-class")

    for name in ("pause", "resume"):
        pr = sub.add_parser(name, help=f"{name} the factory active clock")
        pr.add_argument("--reason")

    sub.add_parser("pipeline", help="the PIPELINE board (read)")
    b = sub.add_parser("brief", help="the triaged daily brief (read)")
    b.add_argument("--day")
    sub.add_parser("killday", help="the kill-day brief (read)")
    venture(sub.add_parser("gatebrief", help="the fixed gate brief for one venture (read)"))
    return p


def _translate(ns: argparse.Namespace):
    """(conductor command name, args, approve-scope|None) for one parsed invocation."""
    cmd = ns.command
    if cmd == "capture":
        args = {"venture_id": ns.venture}
        for key, val in (("codename", ns.codename), ("source", ns.source),
                         ("note_ref", ns.note_ref)):
            if val is not None:
                args[key] = val
        note = _read_note_arg(ns)  # NoteUnreadable propagates: nothing is recorded
        if note:
            args["note"] = note
        if ns.pii:
            args["contains_pii"] = True
        return "capture", args, None
    if cmd == "frame":
        return "frame", {"venture_id": ns.venture, "brief_ref": ns.brief_ref,
                         "score": ns.score, "quotes": ns.quotes}, None
    if cmd == "advise":
        args = {"venture_id": ns.venture}
        if ns.pii:
            args["contains_pii"] = True
        return "advise", args, None  # YELLOW: no token, no --approve
    if cmd == "admit":
        return "admit", {"venture_id": ns.venture}, "admit"
    if cmd == "validate-evidence":
        return "validate.evidence", {"venture_id": ns.venture, "verdict": ns.verdict,
                                     "quote_count": ns.quote_count,
                                     "segment_kind": ns.segment_kind}, None
    if cmd == "validate-experiment":
        args = {"venture_id": ns.venture}
        if ns.channel:
            args["channel"] = ns.channel
        else:
            args.update(metric=ns.metric, actual=ns.actual, threshold=ns.threshold,
                        verdict=ns.verdict)
        return "validate.experiment", args, None
    if cmd == "gate":
        args = {"venture_id": ns.venture, "decision": ns.decision}
        for key, val in (("to", ns.to), ("reason", ns.reason),
                         ("spec_ref", ns.spec_ref), ("fits_days", ns.fits_days)):
            if val is not None:
                args[key] = val
        return "gate", args, "gate"
    if cmd == "kill":
        return "kill", {"venture_id": ns.venture, "reason": ns.reason}, "kill"
    if cmd == "salvage":
        return "salvage", {"venture_id": ns.venture,
                           "asset_types": ns.asset_type or []}, None
    if cmd in ("pause", "resume"):
        return cmd, {"reason": ns.reason or ""}, None
    if cmd == "pipeline":
        return "pipeline", {}, None
    if cmd == "brief":
        return "brief", ({"day": ns.day} if ns.day else {}), None
    if cmd == "killday":
        return "killday", {}, None
    if cmd == "gatebrief":
        return "gatebrief", {"venture_id": ns.venture}, None
    raise CommandUnknown(cmd)  # unreachable — argparse rejects unknown subcommands


class CommandUnknown(Exception):
    """Defensive — argparse's ``required=True`` subparser already rejects this."""


class NoteUnreadable(Exception):
    """``--note-file`` names a path that cannot be read. Raised BEFORE dispatch so a bad
    path never half-captures a venture (fail closed); the message names the path only."""


def _read_note_arg(ns: argparse.Namespace) -> str:
    """The idea text from ``--note`` or ``--note-file`` (the file wins if both are given —
    it is the more deliberate of the two)."""
    if getattr(ns, "note_file", None):
        path = Path(ns.note_file)
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise NoteUnreadable(f"cannot read --note-file {path}: "
                                 f"{type(exc).__name__}") from None
    return getattr(ns, "note", None) or ""


# --- rendering (plain text; the tests grep exact substrings) ----------------------------


def _render(result) -> None:  # noqa: ANN001
    header = f"OK {result.command}  [{result.color}]"
    if result.event_id:
        header += f"  event={result.event_id}"
    print(header)
    data = result.data
    if data is None:
        return
    if isinstance(data, Board):
        _render_board(data)
    elif isinstance(data, DailyBrief):
        _render_daily(data)
    elif isinstance(data, KillDayBrief):
        _render_killday(data)
    elif isinstance(data, GateBrief):
        _render_gatebrief(data)
    elif isinstance(data, WorkflowResult):
        _render_workflow(data)
    else:
        print(f"  {data}")


def _render_workflow(result: WorkflowResult) -> None:
    """An advise run: what was produced, who judged it, and the direction — never the raw
    Critique (its findings hold the critic's full prose; the artifact + gate brief are
    where the long form lives)."""
    print(f"  produced: {result.artifact_ref}  (capability {result.capability}, "
          f"model {result.model})")
    print(f"  critic tier {result.critic_tier} via {result.critique.model} "
          f"— verdict {result.critique.verdict}")
    if result.critique.steer:
        print(f"  steer: {_one_line(result.critique.steer)}")
    else:
        print("  steer: (none — a tier-3 checklist floor gives findings, not direction)")
    print(f"  gate brief is now presentable: charterhouse gatebrief "
          f"--venture {result.artifact_ref.split('/')[1]}")


def _one_line(text: str, limit: int = 300) -> str:
    """Model prose on one bounded line — the full text lives in the vault artifact."""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= limit else flat[:limit] + "…"


def _render_board(board: Board) -> None:
    if not board.rows:
        print("  (empty pipeline)")
    for row in board.rows:
        flags = f"  [{', '.join(row.flags)}]" if row.flags else ""
        print(f"  {row.venture_id}  {row.codename}  {row.state.value}  "
              f"score={row.score}{flags}")


def _render_daily(brief: DailyBrief) -> None:
    if brief.decisions:
        print("  decisions needing you:")
        for d in brief.decisions:
            print(f"    - {d}")
    else:
        print("  silence — nothing needs you today (INV-TRIAGE; a valid answer)")
    for r in brief.red_queue:
        print(f"    ! RED: {r}")
    for day, count in brief.pending_sends:
        print(f"    sends {day}: {count}")


def _render_killday(brief: KillDayBrief) -> None:
    """Worst-first: the calls that end something are read before the routine ones. Each
    row carries its steer, so kill day is a decision list, not just a status board."""
    if not brief.rows and not brief.unbriefable:
        print("  (no active ventures)")
    for gate, rec in brief.rows:
        print(f"  {gate.venture_id}  {gate.codename}  {gate.state.value}  "
              f"→ {rec}  (critic tier {gate.critic.tier})")
        if gate.steer:
            print(f"      steer: {_one_line(gate.steer, 200)}")
        if gate.evidence:
            print(f"      evidence: {', '.join(gate.evidence)}")
    for vid in brief.unbriefable:
        print(f"  {vid}  — unbriefable (no critic take yet; named, never dropped) "
              f"— run: charterhouse advise --venture {vid}")


def _render_gatebrief(gate: GateBrief) -> None:
    print(f"  venture: {gate.venture_id}  ({gate.codename})  state={gate.state.value}")
    print(f"  score={gate.score}  active_in_state={gate.active_in_state}")
    print(f"  recommendation: {gate.recommendation}")
    print(f"  critic tier: {gate.critic.tier}  artifact={gate.critic.artifact_ref}")
    if gate.steer:
        print(f"  steer: {_one_line(gate.steer)}")
    else:
        print("  steer: (none recorded — tier-3 checklist floor, or no advise run yet)")
    if gate.evidence:
        print(f"  evidence: {', '.join(gate.evidence)}")
    if gate.artifacts:
        print(f"  artifacts: {', '.join(gate.artifacts)}")


def main(argv: list[str] | None = None, *, factory=None) -> int:  # noqa: ANN001
    """Parse one command, dispatch through ``Conductor.command``, print, exit.
    Refusals print the OWNER's reason and exit 1 (the halt); ``--approve`` mints the
    founder token at the Gov boundary for the RED commands."""
    argv = list(sys.argv[1:] if argv is None else argv)
    ns = _build_parser().parse_args(argv)

    if factory is None:
        if not ns.data_dir:
            print("error: --data-dir is required (no factory injected)", file=sys.stderr)
            return 2
        load_env_file()  # populate the process environment from .env at startup; no-op if absent
        # The real boot is LIVE: real HTTP transports + the local embedder, so `advise`
        # can actually call a model. Tests never take this path (they inject a factory or
        # call build_factory directly, where the default stays fail-closed).
        factory = build_factory(ns.repo, ns.data_dir, profile=ns.profile, live=True)

    try:
        name, args, scope = _translate(ns)
    except NoteUnreadable as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2  # nothing dispatched, nothing recorded

    tok = None
    if scope is not None and getattr(ns, "approve", False):
        # --approve IS the founder act: mint the single-use grant at the Gov boundary
        # and pass it through — the owner consumes it exactly once (INV-GOV-1/3).
        tok = factory.gov.grant(scope, args.get("venture_id"), TOKEN_TTL_S)

    try:
        result = factory.conductor.command(name, args, tok)
    except (ConductorError, ProjectionsError) as exc:
        # The OWNER's verbatim reason (S5/S6 refusals, INV-COND-2 NoCriticForGate,
        # unknown-venture). Fail closed; the venture does not move.
        print(f"REFUSED {name}: {exc}")
        return 1
    _render(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
