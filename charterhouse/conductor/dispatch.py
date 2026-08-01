"""``Conductor`` — the S12 single chokepoint (docs/10; docs/40 §8; conductor/API.md).

Every command: classify (S6) → enforce guards via the OWNING subsystem → act via the
owner → append (owner's own event, or ONE conductor recorder fact) → projections
re-derive on read. INV-COND-1 is structural: no legality table, no class matrix, no
token semantics, no PII rule lives here — tokens pass through to exactly one owner
boundary (single consumption); refusal reasons are the owner's text verbatim.
INV-COND-3 is structural: no attribute mutates after ``__init__``; the ledger is the
only memory.

Determinism (docs/61 §INV-DET): deterministic given the ledger + injected clock; the
LLM path exists only behind S10's workflow commands; no env read.
"""

from __future__ import annotations

from collections.abc import Mapping

from charterhouse.capabilities.framework import FrameworkError
from charterhouse.contracts.authz import Token
from charterhouse.contracts.events import Event, EventType, LedgerError
from charterhouse.contracts.state import State, Venture
from charterhouse.governance.types import Action
from charterhouse.lifecycle import LifecycleError
from charterhouse.projections import calibration, daily_brief, gate_brief, killday_brief, pipeline

from charterhouse.conductor.types import CommandRefused, CommandResult

__all__ = ["Conductor"]


class Conductor:
    """The chokepoint. Wired with the fully live stack — no stubs (conductor/API.md
    consumed-surface list); constructing it is free of side effects."""

    def __init__(self, *, ledger, registry, lifecycle, gov, memory, workflow,  # noqa: ANN001
                 clock, actor: str = "conductor") -> None:
        self._ledger = ledger
        self._registry = registry
        self._lifecycle = lifecycle
        self._gov = gov
        self._memory = memory
        self._workflow = workflow
        self._clock = clock
        self._actor = actor
        # The dispatch table — built once; never rebound (INV-COND-3 statelessness).
        self._handlers = {
            "capture": self._capture,
            "frame": self._frame,
            "admit": self._admit,
            "validate.evidence": self._validate_evidence,
            "validate.experiment": self._validate_experiment,
            "spend.envelope": self._spend_envelope,
            "spend.meter": self._spend_meter,
            "send.stage": self._send_stage,
            "gate": self._gate,
            "advance.express": self._advance_express,
            "advise": self._advise,
            "shape": self._shape,
            "build": self._build,
            "recruit.partners": self._recruit_partners,
            "deploy.prod": self._deploy_prod,
            "billing.enable": self._billing_enable,
            "launch": self._launch,
            "pivot": self._pivot,
            "graduate": self._graduate,
            "kill": self._kill,
            "salvage": self._salvage,
            "consolidate": self._consolidate,
            "calibrate": self._calibrate,
            "pause": self._pause,
            "resume": self._resume,
            "pipeline": self._pipeline,
            "brief": self._brief,
            "killday": self._killday,
            "gatebrief": self._gatebrief,
        }

    # --- the frozen surface (docs/40 §8) ------------------------------------------------

    def command(self, name: str, args: Mapping | None = None,
                token: Token | None = None) -> CommandResult:
        """Dispatch one command through the five-step pipeline. Refusals raise
        ``CommandRefused`` (the OWNER's reason) / ``NoCriticForGate`` — fail closed;
        pre-act refusals append nothing."""
        args = dict(args or {})
        venture_id = args.get("venture_id")
        action = Action(name=name, venture_id=venture_id, params=args,
                        check=args.get("check"))
        # 1. classify — S6's matrix, never a local copy (unknown → RED, fail closed).
        auth_class = self._gov.classify(action)
        handler = self._handlers.get(name)
        if handler is None:
            decision = self._gov.authorize(action, token)  # S6 denies unknown names
            raise CommandRefused(
                f"unknown command {name!r}: {decision.reason or 'denied by Gov'}")
        # 2–4. guards + act + append — at the OWNING subsystem (INV-COND-1); the
        # owner's typed refusals surface with their own words.
        try:
            event_id, data = handler(args, token, action)
        except (CommandRefused,) as exc:
            raise exc
        except LifecycleError as exc:
            raise CommandRefused(str(exc)) from exc
        except FrameworkError as exc:
            raise CommandRefused(str(exc)) from exc
        except LedgerError as exc:
            raise CommandRefused(str(exc)) from exc
        # 5. projections regenerate on read (nothing cached — INV-COND-3).
        return CommandResult(ok=True, command=name, color=auth_class.color.value,
                             venture_id=venture_id, event_id=event_id, data=data)

    def gate_brief(self, venture_id: str):
        """docs/40 §8: delegate to S13's fixed-schema assembly (INV-COND-2)."""
        return gate_brief(self._ledger, venture_id)

    # --- shared helpers -----------------------------------------------------------------

    def _venture(self, args: Mapping) -> Venture:
        venture_id = args.get("venture_id")
        v = self._registry.get(venture_id) if venture_id else None
        if v is None:
            raise CommandRefused(f"unknown venture {venture_id!r}")
        return v

    def _authorize(self, action: Action, token: Token | None) -> None:
        """S6-owned guard for conductor-recorded facts (GREEN/YELLOW need no token;
        RED/two-key consume theirs here — the single consumption point)."""
        decision = self._gov.authorize(action, token)
        if not decision.ok:
            raise CommandRefused(decision.reason)

    def _append(self, type_: EventType, args: Mapping, payload: dict,
                token: Token | None = None, *, to_state: State | None = None) -> str:
        return self._ledger.append(Event(
            type=type_, actor=self._actor, payload=payload,
            venture_id=args.get("venture_id"),
            to_state=to_state.value if to_state is not None else None,
            authorization=token.id if token is not None else None,
            active_time=self._clock.now_active))

    # --- recorder facts (conductor as the acting-subsystem recorder) --------------------

    def _capture(self, args, token, action):  # noqa: ANN001
        self._authorize(action, token)
        vid = args.get("venture_id")
        if not vid:
            raise CommandRefused("capture requires a venture_id")
        payload = {"source": args.get("source", "inbox"),
                   "note_ref": args.get("note_ref", f"note-{vid}"),
                   "codename": args.get("codename", vid)}
        if args.get("forked_from"):
            payload["forked_from"] = args["forked_from"]
        # The venture's birth record — the ONE recorder fact carrying to_state
        # (IF-1's capture semantics; every other recorder fact is state-neutral).
        return self._append(EventType.CAPTURE, args, payload,
                            to_state=State.CAPTURED), None

    def _validate_evidence(self, args, token, action):  # noqa: ANN001
        self._authorize(action, token)
        payload = {"verdict": args.get("verdict"),
                   "quote_count": args.get("quote_count"),
                   "segment_kind": args.get("segment_kind")}
        return self._append(EventType.EVIDENCE_GATE, args, payload), None

    def _validate_experiment(self, args, token, action):  # noqa: ANN001
        self._authorize(action, token)
        if args.get("channel"):
            payload = {"channel": args["channel"],
                       "experiment_live_at": self._clock.now_active}
            return self._append(EventType.EXPERIMENT_LIVE, args, payload), None
        if args.get("metric"):
            payload = {"metric": args["metric"], "actual": args.get("actual"),
                       "threshold": args.get("threshold"),
                       "verdict": args.get("verdict")}
            return self._append(EventType.EXPERIMENT_RESULT, args, payload), None
        raise CommandRefused(
            "validate.experiment requires 'channel' (go-live) or 'metric' (result)")

    def _recruit_partners(self, args, token, action):  # noqa: ANN001
        self._authorize(action, token)
        payload = {"recruited_count": int(args.get("recruited_count") or 0)}
        return self._append(EventType.PARTNERS, args, payload), None

    def _salvage(self, args, token, action):  # noqa: ANN001
        kinds = [str(k) for k in (args.get("asset_types") or []) if str(k).strip()]
        if not kinds:
            raise CommandRefused(
                "salvage requires asset_types naming at least one salvaged asset "
                "(R-SALVAGE-TYPES; anti_pattern is first-class)")
        self._authorize(action, token)
        return self._append(EventType.SALVAGE, args, {"asset_types": kinds}), None

    # --- S6-owned commands --------------------------------------------------------------

    def _spend_envelope(self, args, token, action):  # noqa: ANN001
        receipt = self._gov.envelope_open(args.get("venture_id"),
                                          float(args.get("cap_usd") or 0.0))
        return None, receipt

    def _spend_meter(self, args, token, action):  # noqa: ANN001
        result = self._gov.spend(args.get("venture_id"),
                                 float(args.get("amount") or 0.0))
        if not result.ok:
            raise CommandRefused(result.reason)
        return None, result

    def _send_stage(self, args, token, action):  # noqa: ANN001
        self._authorize(action, token)
        payload = {"count": int(args.get("count") or 0),
                   "audience_tz": args.get("audience_tz", "UTC"),
                   "per_domain": args.get("per_domain", {})}
        return self._append(EventType.SEND_BATCH, args, payload, token), None

    def _deploy_prod(self, args, token, action):  # noqa: ANN001
        self._authorize(action, token)  # RED two-key — S6 verifies both keys
        return self._append(EventType.DEPLOY_PROD, args,
                            {"tag": args.get("tag")}, token), None

    def _billing_enable(self, args, token, action):  # noqa: ANN001
        self._authorize(action, token)
        return self._append(EventType.BILLING_ENABLE, args, {}, token), None

    def _launch(self, args, token, action):  # noqa: ANN001
        self._authorize(action, token)
        return self._append(EventType.LAUNCH, args,
                            {"kit_ref": args.get("kit_ref")}, token), None

    # --- S5-owned commands (token passes through; S5 authorizes at its boundary) --------

    def _frame(self, args, token, action):  # noqa: ANN001
        v = self._venture(args)
        payload = {"brief_ref": args.get("brief_ref"), "score": args.get("score"),
                   "quotes": args.get("quotes")}
        result = self._lifecycle.transition(v, State.FRAMED, payload=payload)
        return result.event_id, result

    def _admit(self, args, token, action):  # noqa: ANN001
        result = self._lifecycle.transition(self._venture(args), State.VALIDATING,
                                            token)
        return result.event_id, result

    def _advance_express(self, args, token, action):  # noqa: ANN001
        to = State(args["to"])
        result = self._lifecycle.transition(self._venture(args), to, token,
                                            express=True)
        return result.event_id, result

    def _graduate(self, args, token, action):  # noqa: ANN001
        result = self._lifecycle.transition(self._venture(args), State.GRADUATED,
                                            token)
        return result.event_id, result

    def _kill(self, args, token, action):  # noqa: ANN001
        result = self._lifecycle.transition(self._venture(args), State.KILLED, token,
                                            reason=args.get("reason"))
        return result.event_id, result

    def _pivot(self, args, token, action):  # noqa: ANN001
        result = self._lifecycle.pivot(
            self._venture(args), token, new_id=args["new_id"],
            codename=args.get("codename", args["new_id"]),
            inherited=args.get("inherited", {}), reason=args.get("reason", ""))
        return result.events[-1], result

    def _pause(self, args, token, action):  # noqa: ANN001
        return self._lifecycle.pause(args.get("reason", "")), None

    def _resume(self, args, token, action):  # noqa: ANN001
        return self._lifecycle.resume(args.get("reason", "")), None

    def _gate(self, args, token, action):  # noqa: ANN001
        """The founder verdict (docs/05 five levers): brief first (critic mandatory,
        INV-COND-2) → act via S5 → record the ONE gate_decision."""
        v = self._venture(args)
        brief = gate_brief(self._ledger, v.id)  # NoCriticForGate propagates
        decision = str(args.get("decision", "")).upper()
        if decision == "ADVANCE":
            to = State(args["to"])
            if to is State.BUILDING and args.get("spec_ref"):
                # docs/05 cut-list: the spec approval and the advance are ONE founder
                # decision under ONE token — the fact first (the S5 guard reads it),
                # the token consumed once, inside S5 (IMPLEMENTATION §6.2).
                self._append(EventType.SPEC_APPROVED, args,
                             {"spec_ref": args["spec_ref"],
                              "fits_days": args.get("fits_days")}, token)
            result = self._lifecycle.transition(v, to, token)
            acted = result.event_id
        elif decision == "KILL":
            result = self._lifecycle.transition(v, State.KILLED, token,
                                                reason=args.get("reason"))
            acted = result.event_id
        elif decision == "OMW":
            acted = self._lifecycle.grant_omw(v, token)
        else:
            raise CommandRefused(
                f"gate decision must be ADVANCE, KILL, or OMW — got {decision!r}")
        decision_id = self._append(
            EventType.GATE_DECISION, args,
            {"brief_ref": f"brief:{v.id}:{brief.state.value}",
             "recommendation": brief.recommendation,
             "decision": decision,
             "critic_tier": brief.critic.tier}, token)
        return decision_id, brief

    # --- S10-owned workflow commands ----------------------------------------------------

    def _run_workflow(self, args, state: State):  # noqa: ANN001
        v = self._venture(args)
        result = self._workflow.run(state, v, require=self._require(args))
        return result.event_id, result

    @staticmethod
    def _require(args):  # noqa: ANN001
        """The per-run routing constraint. ``contains_pii`` confines BOTH LLM beats to
        local models (INV-PII-3); absent, the row's own constraint applies."""
        if not args.get("contains_pii"):
            return None
        from charterhouse.router.types import Require

        return Require(contains_pii=True)

    def _advise(self, args, token, action):  # noqa: ANN001
        """Run the venture's CURRENT-state workflow (PRODUCE→CRITIQUE) and record the
        critic take, so a gate becomes presentable (INV-COND-2). YELLOW, not RED: this is
        an AI opinion, not a founder decision — it moves no venture (the CHECKPOINT event
        is state-neutral by construction) and crosses no gate. A state with no workflow row
        surfaces S10's ``UnknownWorkflow`` unchanged (fail closed)."""
        return self._run_workflow(args, self._venture(args).state)

    def _shape(self, args, token, action):  # noqa: ANN001
        return self._run_workflow(args, State.SHAPING)

    def _build(self, args, token, action):  # noqa: ANN001
        return self._run_workflow(args, State.BUILDING)

    # --- S9-owned -----------------------------------------------------------------------

    def _consolidate(self, args, token, action):  # noqa: ANN001
        return None, self._memory.consolidate()

    # --- S13 pure reads -----------------------------------------------------------------

    def _pipeline(self, args, token, action):  # noqa: ANN001
        return None, pipeline(self._ledger)

    def _brief(self, args, token, action):  # noqa: ANN001
        return None, daily_brief(self._ledger, args.get("day"))

    def _killday(self, args, token, action):  # noqa: ANN001
        return None, killday_brief(self._ledger)

    def _gatebrief(self, args, token, action):  # noqa: ANN001
        return None, gate_brief(self._ledger, args.get("venture_id"))

    def _calibrate(self, args, token, action):  # noqa: ANN001
        return None, calibration(self._ledger)
