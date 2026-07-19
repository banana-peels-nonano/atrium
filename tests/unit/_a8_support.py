"""A8-local test support for the S10 (Framework) suite — PROVISIONAL.

The full LIVE stack (docs/55 conventions, no stubs): real Config over fixture dirs,
real tmp-path Ledger, real Security, real Memory (LanceDB tmp + FakeEmbedder via
``_a7_support``), real Router with A11 ``FakeProvider`` transports — **no network
anywhere** (INV-TEST-SAFE). Model ids span distinct families (llama/deepseek/gemini/
claude) so the INV-WF-2 ladder is exercisable; probe doubles follow the A7 R10 pattern.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from charterhouse.capabilities.framework import (
    CapabilitySpec,
    Workflow,
    WorkflowRegistry,
    WorkflowSpec,
)
from charterhouse.config import Config
from charterhouse.contracts.events import Event, EventType
from charterhouse.contracts.state import State, Venture
from charterhouse.ledger import Ledger
from charterhouse.router.facade import Router
from charterhouse.router.types import ProvidersExhausted
from charterhouse.security import Security
from charterhouse.security.types import CheckpointError

from tests.fakes import FakeProvider, ProviderError
from tests.fixtures.pii_corpus import KNOWN_IDENTITIES
from tests.unit import _a2_support as a2
from tests.unit import _a3_support as a3
from tests.unit import _a7_support as a7

# --- fixture catalog: model ids spanning DISTINCT families (INV-WF-2) ---------------------

PROVIDERS: dict = {
    "ollama": {"base_url": "http://localhost:11434/v1", "key_env": "OLLAMA_HOST",
               "kind": "local"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1",
                   "key_env": "OPENROUTER_API_KEY", "kind": "cloud"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "key_env": "GEMINI_API_KEY", "kind": "cloud"},
}

MODELS: dict = {
    "llama3-local": {"provider": "ollama", "ctx": 8192, "price_in": 0.0,
                     "price_out": 0.0, "tier": "free", "good_at": ["draft"]},
    "llama3-big": {"provider": "openrouter", "ctx": 131072, "price_in": 0.0,
                   "price_out": 0.0, "tier": "free",
                   "good_at": ["reasoning", "critique"]},
    "deepseek-chat-free": {"provider": "openrouter", "ctx": 65536, "price_in": 0.0,
                           "price_out": 0.0, "tier": "free",
                           "good_at": ["reasoning", "critique"]},
    "gemini-flash": {"provider": "gemini", "ctx": 1000000, "price_in": 0.0,
                     "price_out": 0.0, "tier": "free",
                     "good_at": ["reasoning", "critique", "web"]},
}

# Producer: draft → llama3-local (family "llama"). Critic variants per test:
ROUTES: dict = {
    "draft": {"primary": "llama3-local", "fallback": []},
    "critic": {"primary": "deepseek-chat-free", "fallback": ["gemini-flash"]},
}
ROUTES_SAMEFAM: dict = {  # critic lands the producer's family, different model → tier 2
    "draft": {"primary": "llama3-local", "fallback": []},
    "critic": {"primary": "llama3-big", "fallback": []},
}
ROUTES_SELF: dict = {  # critic lands the EXACT producer model → tier 3 (self-critique)
    "draft": {"primary": "llama3-local", "fallback": []},
    "critic": {"primary": "llama3-local", "fallback": []},
}

BUDGETS: dict = {"monthly_usd": 20.0, "on_exceeded": "degrade", "send_daily": 40}

SCOUT_SPEC = CapabilitySpec(
    name="scout",
    mission="Find and frame venture candidates from captured signals",
    scope="Scan captured notes; frame problem, segment, and channel hypotheses",
    inputs=("captured note",),
    outputs=("brief", "score"),
    memory_read=("anti_pattern", "segment"),
    memory_write=("brief",),
    escalation="Flag thin evidence to the founder gate",
)

VID = "v-cap"


def workflow_spec(**kw) -> WorkflowSpec:
    """The fixture table row: scout on CAPTURED, FRAME as the (state-neutral) domain
    event — override any field."""
    defaults: dict = {"capability": SCOUT_SPEC, "role": "draft",
                      "event_type": EventType.FRAME, "artifact_name": "scout-brief",
                      "k": 3, "retries": 2}
    defaults.update(kw)
    return WorkflowSpec(**defaults)


# --- programmable doubles (A7 R10 probe pattern) ------------------------------------------


class SwitchableProvider(FakeProvider):
    """A ``FakeProvider`` with a live ``fail`` switch — flip mid-test to take a
    provider down between beats."""

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.fail = False

    def complete(self, model, messages, tools=None, max_tokens=None):  # noqa: ANN001
        if self.fail:
            raise ProviderError(f"{model}: switched off (probe)")
        return super().complete(model, messages, tools, max_tokens)


class RecordingProvider(FakeProvider):
    """Records every ``messages`` payload — proves what PRODUCE actually saw."""

    def __init__(self, **kw) -> None:
        super().__init__(**kw)
        self.seen: list[list] = []

    def complete(self, model, messages, tools=None, max_tokens=None):  # noqa: ANN001
        self.seen.append(messages)
        return super().complete(model, messages, tools, max_tokens)


class FlakyLLM:
    """Wraps the real ``LLMClient``: the first ``failures`` calls raise the real
    ``ProvidersExhausted``, then delegates — probes the runner's retry loop at its
    consumed seam without fighting S8's own failover resilience."""

    def __init__(self, inner, failures: int) -> None:  # noqa: ANN001
        self._inner = inner
        self._failures = failures
        self.calls = 0

    def call(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.calls += 1
        if self.calls <= self._failures:
            raise ProvidersExhausted("flaky probe: providers down")
        return self._inner.call(*args, **kwargs)


class RefusingSecurity(Security):
    """A ``Security`` whose checkpoint always fails closed — the INV-WF-1 partial-state
    probe (never used to test S7 itself)."""

    def checkpoint(self, text: str, doc_id: str | None = None):
        raise CheckpointError("probe: residual finding kinds only")


# --- the live stack -----------------------------------------------------------------------


def seed_captured(ledger: Ledger, vid: str = VID, codename: str = "pods") -> None:
    """History fixture: one capture event so the venture exists in the replay."""
    ledger.append(Event(type=EventType.CAPTURE, actor="test",
                        payload={"codename": codename}, venture_id=vid,
                        to_state=State.CAPTURED.value, active_time=0))


def make_stack(tmp_path: Path, *, routes: dict | None = None,
               models: dict | None = None,
               transports: dict | None = None, ledger: Ledger | None = None,
               security: Security | None = None, llm=None,  # noqa: ANN001
               state: State = State.CAPTURED, seed: bool = True) -> SimpleNamespace:
    """(workflow, llm, ledger, memory, security, transports, venture, spec, vault_dir)
    over the fully live stack. Override any seam per test."""
    cfg_dir = a2.write_config(tmp_path / "cfg", providers=PROVIDERS,
                              models=models if models is not None else MODELS,
                              routes=routes if routes is not None else ROUTES,
                              profiles={"free": {}}, budgets=BUDGETS)
    config = Config.load(cfg_dir, profile="free")
    if ledger is None:
        ledger = Ledger(tmp_path / "ledger", new_id=a3.deterministic_id_factory())
    t = {pid: FakeProvider(canned=f"draft brief and score from {pid}")
         for pid in PROVIDERS}
    if transports:
        t.update(transports)
    router = Router(config, ledger, transports=t)
    the_llm = llm if llm is not None else router
    vault_dir = tmp_path / "vault"
    if security is None:
        security = Security(vault_dir, known_identities=KNOWN_IDENTITIES)
    mem = a7.make_memory(tmp_path, ledger=ledger)
    spec = workflow_spec()
    registry = WorkflowRegistry({state: spec})
    workflow = Workflow(registry, the_llm, mem.memory, security, ledger, vault_dir,
                        family_of=lambda mid: config.get_model(mid).family)
    if seed:
        seed_captured(ledger)
    venture = Venture(id=VID, codename="pods", state=state, active_time_accum=10)
    return SimpleNamespace(workflow=workflow, llm=the_llm, router=router,
                           ledger=ledger, memory=mem.memory, mem=mem,
                           security=security, transports=t, venture=venture,
                           spec=spec, registry=registry, vault_dir=vault_dir,
                           config=config)


# --- event taxonomy helpers (IMPLEMENTATION §6.5) -----------------------------------------

TELEMETRY_TYPES = {EventType.LLM_CALL, EventType.ERROR, EventType.PII_BLOCK}


def domain_events(ledger: Ledger, *, exclude_seed: bool = True) -> list[Event]:
    """Non-telemetry events — the INV-WF-1 mutation surface (minus the seed capture)."""
    out = [e for e in ledger.read() if e.type not in TELEMETRY_TYPES]
    if exclude_seed:
        out = [e for e in out if e.type is not EventType.CAPTURE]
    return out


def vault_artifacts(vault_dir: Path) -> list[Path]:
    """Every venture artifact file under the vault (doctrine/sidecar areas excluded)."""
    ventures = vault_dir / "ventures"
    return sorted(p for p in ventures.rglob("*") if p.is_file()) if ventures.is_dir() else []


# --- fixture neutral-spec markdown (the frozen format) ------------------------------------


def spec_markdown(*, drop_section: str | None = None,
                  drop_literal: str | None = None) -> str:
    """A valid ``*.agent.md`` body; optionally remove a required piece (loader tests)."""
    sections = {
        "Mission": "Find and frame venture candidates from captured signals.",
        "Scope": "Scan captured notes; frame problem, segment, and channel hypotheses.",
        "Inputs": "- captured note",
        "Outputs": "- brief\n- score",
        "Memory Scope": "READ: anti_pattern, segment\nWRITE: brief",
        "Escalation": "Flag thin evidence to the founder gate.",
    }
    if drop_section:
        del sections[drop_section]
    tail = "This capability has no authority and is stateless."
    if drop_literal == "no authority":
        tail = "This capability is stateless."
    elif drop_literal == "stateless":
        tail = "This capability has no authority."
    body = "# scout — capability contract\n\n"
    body += "\n\n".join(f"## {h}\n{t}" for h, t in sections.items())
    return body + "\n\n" + tail + "\n"
