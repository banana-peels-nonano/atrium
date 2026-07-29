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
from charterhouse.conductor.types import ConductorError
from charterhouse.config import Config
from charterhouse.env import load_env_file
from charterhouse.governance import Gov
from charterhouse.ledger import Ledger
from charterhouse.lifecycle import FactoryClock, Lifecycle
from charterhouse.memory import Memory, MemoryStore, RetrievalWeights
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

# The local embedder's real pins (docs/33) — carried by the v1 stub so the store's
# INV-MEM-2 marker is correct for when the ops phase wires the live OllamaEmbedder.
EMBED_MODEL = "nomic-embed-text"
EMBED_DIM = 768


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
                  transports: dict | None = None,
                  known_identities: tuple[str, ...] = ()):
    """Wire the fully live factory (the composition root): real Config over the
    committed ``config/``, real Ledger/Registry/Gov/Lifecycle/Security/Memory/
    Workflow/Conductor — no stubs beyond the two fail-closed transport seams.
    ``embedder``/``transports`` are injection seams (tests pass fakes; production
    defaults are the fail-closed ``NoEmbedder``/``NoTransport`` until the ops phase)."""
    repo_root = Path(repo_root)
    data_dir = Path(data_dir)
    vault_dir = Path(vault_dir) if vault_dir is not None else data_dir / "vault"

    config = Config.load(repo_root / "config", profile)
    ledger = Ledger(data_dir / "ledger")
    registry = Registry(ledger)
    clock = FactoryClock()  # active-time; the Conductor's deterministic clock
    gov = Gov(ledger, config, clock=time.time)  # wall clock for token TTL + timestamps
    lifecycle = Lifecycle(ledger, registry, gov, clock)
    security = Security(vault_dir, known_identities=known_identities)

    if embedder is None:
        embedder = NoEmbedder(embed_model)
    store = MemoryStore.open(data_dir / "vectors", embed_model, embedder.dim)
    memory = Memory(store, embedder, ledger, Scanner(known_identities),
                    vault_dir / "memory" / "DOCTRINE.md",
                    weights=RetrievalWeights.from_config(config.memory))

    if transports is None:
        provider_ids = {config.get_model(mid).provider for mid in config.models()}
        transports = {pid: NoTransport() for pid in provider_ids}
    router = Router(config, ledger, transports=transports)

    workflow = Workflow(build_registry(repo_root / "agents"), router, memory, security,
                        ledger, vault_dir,
                        family_of=lambda mid: config.get_model(mid).family)
    conductor = Conductor(ledger=ledger, registry=registry, lifecycle=lifecycle,
                          gov=gov, memory=memory, workflow=workflow, clock=clock)
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

    f = venture(sub.add_parser("frame", help="frame a captured venture (→FRAMED)"))
    f.add_argument("--brief-ref", required=True)
    f.add_argument("--score", type=int, required=True)
    f.add_argument("--quotes", type=int, required=True)

    a = venture(sub.add_parser("admit", help="admit to validation (RED — needs --approve)"))
    a.add_argument("--approve", action="store_true")

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
        return "capture", args, None
    if cmd == "frame":
        return "frame", {"venture_id": ns.venture, "brief_ref": ns.brief_ref,
                         "score": ns.score, "quotes": ns.quotes}, None
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
    else:
        print(f"  {data}")


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
    for gate, rec in brief.rows:
        print(f"  {gate.venture_id}  {gate.codename}  {gate.state.value}  "
              f"→ {rec}  (critic tier {gate.critic.tier})")
    for vid in brief.unbriefable:
        print(f"  {vid}  — unbriefable (no critic take yet; named, never dropped)")


def _render_gatebrief(gate: GateBrief) -> None:
    print(f"  venture: {gate.venture_id}  ({gate.codename})  state={gate.state.value}")
    print(f"  score={gate.score}  active_in_state={gate.active_in_state}")
    print(f"  recommendation: {gate.recommendation}")
    print(f"  critic tier: {gate.critic.tier}  artifact={gate.critic.artifact_ref}")
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
        factory = build_factory(ns.repo, ns.data_dir, profile=ns.profile)

    name, args, scope = _translate(ns)

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
