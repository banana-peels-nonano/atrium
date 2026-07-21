"""A10-local test support for the S12/S13 suites — PROVISIONAL.

``make_factory`` wires the WHOLE live stack (docs/55 conventions, no stubs): real
Config/Ledger/Registry/Lifecycle/Gov/Security/Memory/Router/Workflow behind the real
Conductor — A11's ``FakeProvider`` is every transport, ``FakeEmbedder`` behind Memory
(**no network anywhere**, INV-TEST-SAFE). Founder tokens are minted ONLY at the Gov
boundary (``factory.tok(scope, vid)``). Spy wrappers (delegating, counting) prove the
INV-COND-1 call paths; event seeders extend the ``_a3/_a4`` helper conventions.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from charterhouse.capabilities.framework import Workflow
from charterhouse.conductor import Conductor, build_registry
from charterhouse.config import Config
from charterhouse.contracts.events import Event, EventType
from charterhouse.contracts.state import State
from charterhouse.governance import Gov
from charterhouse.ledger import Ledger
from charterhouse.lifecycle import FactoryClock, Lifecycle
from charterhouse.registry.facade import Registry
from charterhouse.router.facade import Router
from charterhouse.security import Security

from tests.fakes import FakeProvider
from tests.fixtures.pii_corpus import KNOWN_IDENTITIES
from tests.unit import _a3_support as a3
from tests.unit import _a7_support as a7
from tests.unit import _a8_support as a8

AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"
TTL = 3600.0


class SpyGov(Gov):
    """A delegating Gov that counts classify/authorize — proves decisions transit S6."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__(*args, **kwargs)
        self.classified: list[str] = []
        self.authorized: list[str] = []

    def classify(self, action):  # noqa: ANN001
        self.classified.append(action.name)
        return super().classify(action)

    def authorize(self, action, token):  # noqa: ANN001
        self.authorized.append(action.name)
        return super().authorize(action, token)


class SpyLifecycle(Lifecycle):
    """A delegating Lifecycle that counts transitions — proves acts transit S5."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__(*args, **kwargs)
        self.transitions: list[tuple[str, str]] = []

    def transition(self, v, to, token=None, **kwargs):  # noqa: ANN001, ANN003
        self.transitions.append((v.id, to.value))
        return super().transition(v, to, token, **kwargs)


def make_factory(tmp_path: Path, *, ledger: Ledger | None = None) -> SimpleNamespace:
    """The full live factory. Returns every seam plus the wired Conductor."""
    cfg_dir = a8.a2.write_config(tmp_path / "cfg", providers=a8.PROVIDERS,
                                 models=a8.MODELS, routes=a8.ROUTES,
                                 profiles={"free": {}}, budgets=a8.BUDGETS)
    config = Config.load(cfg_dir, profile="free")
    if ledger is None:
        ledger = Ledger(tmp_path / "ledger", new_id=a3.deterministic_id_factory())
    registry = Registry(ledger)
    clock = FactoryClock()
    gov = SpyGov(ledger, config, clock=lambda: 0.0)
    lifecycle = SpyLifecycle(ledger, registry, gov, clock)
    vault_dir = tmp_path / "vault"
    security = Security(vault_dir, known_identities=KNOWN_IDENTITIES)
    mem = a7.make_memory(tmp_path, ledger=ledger)
    transports = {pid: FakeProvider(canned=f"artifact draft from {pid}")
                  for pid in a8.PROVIDERS}
    router = Router(config, ledger, transports=transports)
    workflow = Workflow(build_registry(AGENTS_DIR), router, mem.memory, security,
                        ledger, vault_dir,
                        family_of=lambda mid: config.get_model(mid).family)
    conductor = Conductor(ledger=ledger, registry=registry, lifecycle=lifecycle,
                          gov=gov, memory=mem.memory, workflow=workflow, clock=clock)
    return SimpleNamespace(conductor=conductor, ledger=ledger, registry=registry,
                           lifecycle=lifecycle, gov=gov, security=security,
                           memory=mem.memory, mem=mem, workflow=workflow,
                           router=router, transports=transports, config=config,
                           clock=clock, vault_dir=vault_dir)


def tok(f: SimpleNamespace, scope: str, vid: str | None):
    """Mint one founder token at the Gov boundary (the ONLY minting path in tests)."""
    return f.gov.grant(scope, vid, TTL)


# --- event seeders (the _a3/_a4 convention, extended for S13 fixtures) --------------------


def seed_artifact_produced(ledger: Ledger, vid: str, *, tier: int = 1,
                           ref: str | None = None, capability: str = "scout",
                           active_time: int = 0) -> str:
    return ledger.append(Event(
        type=EventType.ARTIFACT_PRODUCED, actor="system",
        payload={"artifact_ref": ref or f"ventures/{vid}/brief.md",
                 "capability": capability, "critic_tier": tier},
        venture_id=vid, active_time=active_time))


def seed_gate_decision(ledger: Ledger, vid: str, *, tier: int = 2,
                       decision: str = "ADVANCE", active_time: int = 0) -> str:
    return ledger.append(Event(
        type=EventType.GATE_DECISION, actor="conductor",
        payload={"brief_ref": f"brief:{vid}", "recommendation": "HOLD",
                 "decision": decision, "critic_tier": tier},
        venture_id=vid, active_time=active_time))


def seed_override(ledger: Ledger, vid: str, *, kind: str = "override",
                  active_time: int = 0) -> str:
    etype = EventType.OVERRIDE if kind == "override" else EventType.SCORE_OVERRIDE
    payload = ({"recommendation": "KILL", "decision": "ADVANCE", "reason": "gut"}
               if kind == "override" else
               {"old_score": 14, "new_score": 20, "reason": "founder conviction"})
    return ledger.append(Event(type=etype, actor="founder", payload=payload,
                               venture_id=vid, active_time=active_time))


def check_pass(name: str = "payment-path"):
    """A passing two-key automated check (INV-GOV-2's second key)."""
    from charterhouse.governance.types import CheckResult

    return CheckResult(name=name, passed=True, detail="probe check passed")
