"""S6 Governance unit suite — INV-GOV-1..6 (docs/14, docs/54 §S6; governance/TESTPLAN.md).

Conventions follow the A3 suite: real tmp-path Ledger (no fake), injected deterministic
clock, typed fail-closed errors via ``pytest.raises``, INV mapping in docstrings, seeded
parametrize property tests against an independent oracle.
"""

from __future__ import annotations

import pytest

from charterhouse.contracts.authz import ActionColor, Token
from charterhouse.contracts.events import EventType
from charterhouse.governance import (
    Action,
    CheckResult,
    Gov,
    MissingReason,
)
from charterhouse.ledger import EventFilter, Ledger

from tests.unit import _a3_support as a3
from tests.unit import _a5_support as sup

# The complete docs/40 §8 command vocabulary -> (color, two_key), per the frozen docs/14
# matrix as recorded in governance/IMPLEMENTATION §3. This test table is the contract.
EXPECTED_MATRIX: dict[str, tuple[ActionColor, bool]] = {
    # GREEN — reversible, no external effect, capped inference
    "capture": (ActionColor.GREEN, False),
    "frame": (ActionColor.GREEN, False),
    "validate.evidence": (ActionColor.GREEN, False),
    "shape": (ActionColor.GREEN, False),
    "recruit.partners": (ActionColor.GREEN, False),
    "salvage": (ActionColor.GREEN, False),
    "consolidate": (ActionColor.GREEN, False),
    "calibrate": (ActionColor.GREEN, False),
    "pause": (ActionColor.GREEN, False),
    "resume": (ActionColor.GREEN, False),
    "pipeline": (ActionColor.GREEN, False),
    "brief": (ActionColor.GREEN, False),
    "killday": (ActionColor.GREEN, False),
    "gatebrief": (ActionColor.GREEN, False),
    # YELLOW — metered/internal within budget
    "spend.meter": (ActionColor.YELLOW, False),
    "validate.experiment": (ActionColor.YELLOW, False),
    "build": (ActionColor.YELLOW, False),
    # RED — money out / production / contact / lifecycle gate
    "admit": (ActionColor.RED, False),
    "gate": (ActionColor.RED, False),
    "advance.express": (ActionColor.RED, False),
    "spend.envelope": (ActionColor.RED, False),
    "send.stage": (ActionColor.RED, False),  # two-key when scaled — asserted separately
    "launch": (ActionColor.RED, False),
    "pivot": (ActionColor.RED, False),
    "graduate": (ActionColor.RED, False),
    "kill": (ActionColor.RED, False),
    # RED two-key (INV-GOV-2 set)
    "deploy.prod": (ActionColor.RED, True),
    "billing.enable": (ActionColor.RED, True),
}


@pytest.fixture
def clock() -> sup.SteppableClock:
    return sup.SteppableClock()


@pytest.fixture
def make_gov(tmp_path, clock):
    """(gov, ledger) factory over a tmp-path real Ledger; FakeConfig budgets injectable."""

    def make(send_daily: int = 40, subdir: str = "ledger") -> tuple[Gov, Ledger]:
        ledger = Ledger(tmp_path / subdir, new_id=a3.deterministic_id_factory())
        gov = Gov(ledger, sup.FakeConfig(send_daily=send_daily), clock=clock)
        return gov, ledger

    return make


def record_send(gov: Gov, ledger: Ledger, clock, venture: str, count: int):
    """Drive one authorized send: grant -> authorize -> (acting subsystem) append
    send_batch carrying the consumed token id (governance/IMPLEMENTATION §6)."""
    tok = gov.grant("send.stage", venture, 3600.0)
    check = CheckResult("deliverability", True) if count > 25 else None
    action = Action("send.stage", venture_id=venture, params={"count": count}, check=check)
    decision = gov.authorize(action, tok)
    if decision.ok:
        ledger.append(sup.send_batch_event(venture, count, tok.id, sup.iso(clock())))
    return decision


# --- classification (the frozen matrix) -----------------------------------------------------


def test_classify_matrix_frozen(make_gov):
    """Every docs/40 §8 command maps to its documented class; the two-key set is exactly
    {deploy.prod, billing.enable, scaled send.stage} (docs/14 matrix, docs/54 §S6)."""
    gov, _ = make_gov()
    for name, (color, two_key) in EXPECTED_MATRIX.items():
        auth = gov.classify(Action(name, venture_id="v1"))
        assert auth.color is color, f"{name}: expected {color}, got {auth.color}"
        assert auth.two_key is two_key, f"{name}: expected two_key={two_key}"
    # Scaled outreach flips send.stage to two-key (INV-GOV-2 "scaled outreach").
    small = gov.classify(Action("send.stage", venture_id="v1", params={"count": 10}))
    scaled = gov.classify(Action("send.stage", venture_id="v1", params={"count": 26}))
    assert (small.color, small.two_key) == (ActionColor.RED, False)
    assert (scaled.color, scaled.two_key) == (ActionColor.RED, True)


def test_classify_unknown_action_fail_closed(make_gov, clock):
    """An unknown action name classifies RED, and authorize denies it even when presented
    with a token minted for that very scope (fail closed; governance/RISKS R6)."""
    gov, _ = make_gov()
    assert gov.classify(Action("mint.nft", venture_id="v1")).color is ActionColor.RED
    tok = gov.grant("mint.nft", "v1", 3600.0)
    decision = gov.authorize(Action("mint.nft", venture_id="v1"), tok)
    assert not decision.ok and decision.reason


def test_green_yellow_need_no_token(make_gov):
    """GREEN and YELLOW actions are autonomous-within-rules: authorize ok with token=None
    and nothing consumed (docs/14 class semantics)."""
    gov, _ = make_gov()
    assert gov.authorize(Action("capture", venture_id="v1"), None).ok
    assert gov.authorize(Action("frame", venture_id="v1"), None).ok
    assert gov.authorize(Action("spend.meter", venture_id="v1"), None).ok
    assert gov.authorize(Action("build", venture_id="v1"), None).ok


# --- tokens (INV-GOV-1, INV-GOV-3) -----------------------------------------------------------


def test_red_requires_valid_scoped_token(make_gov, clock):
    """INV-GOV-1: RED denies with no token, a forged token (never issued here), a token for a
    different action (scope), and a token for a different venture; a correct grant passes."""
    gov, _ = make_gov()
    action = Action("kill", venture_id="v1")

    assert not gov.authorize(action, None).ok
    forged = Token(id="tok-forged", scope="kill", venture_id="v1",
                   issued_at=clock(), expires_at=clock() + 3600.0)
    assert not gov.authorize(action, forged).ok
    wrong_scope = gov.grant("launch", "v1", 3600.0)
    assert not gov.authorize(action, wrong_scope).ok
    wrong_venture = gov.grant("kill", "v2", 3600.0)
    assert not gov.authorize(action, wrong_venture).ok

    valid = gov.grant("kill", "v1", 3600.0)
    assert gov.authorize(action, valid).ok


def test_token_single_use_reuse_refused(make_gov, clock):
    """INV-GOV-3 single-use: a consumed token is refused on re-presentation; and a *denial*
    does not burn a live grant (the founder's approval survives a failed precondition)."""
    gov, _ = make_gov()
    action = Action("kill", venture_id="v1")
    tok = gov.grant("kill", "v1", 3600.0)
    assert gov.authorize(action, tok).ok
    reuse = gov.authorize(action, tok)
    assert not reuse.ok and reuse.reason

    # Denial does not consume: a two-key deny (missing check) leaves the token usable.
    deploy = gov.grant("deploy.prod", "v1", 3600.0)
    denied = gov.authorize(Action("deploy.prod", venture_id="v1"), deploy)
    assert not denied.ok
    ok = gov.authorize(
        Action("deploy.prod", venture_id="v1", check=CheckResult("payment-path", True)),
        deploy,
    )
    assert ok.ok


def test_token_expires(make_gov, clock):
    """INV-GOV-3 expiry: a token past ``expires_at`` on the injected clock is refused; a
    fresh grant authorizes."""
    gov, _ = make_gov()
    action = Action("kill", venture_id="v1")
    tok = gov.grant("kill", "v1", 100.0)
    clock.advance(101.0)
    assert not gov.authorize(action, tok).ok
    fresh = gov.grant("kill", "v1", 100.0)
    assert gov.authorize(action, fresh).ok


# --- two-key (INV-GOV-2) ---------------------------------------------------------------------


def test_two_key_requires_token_and_check(make_gov):
    """INV-GOV-2: deploy.prod / billing.enable need token AND a passing automated check —
    a valid token with a missing or failing check is denied."""
    gov, _ = make_gov()
    for name, check_name in (("deploy.prod", "payment-path"), ("billing.enable", "billing-sim")):
        tok = gov.grant(name, "v1", 3600.0)
        assert not gov.authorize(Action(name, venture_id="v1"), tok).ok
        assert not gov.authorize(
            Action(name, venture_id="v1", check=CheckResult(check_name, False)), tok
        ).ok
        assert gov.authorize(
            Action(name, venture_id="v1", check=CheckResult(check_name, True)), tok
        ).ok


def test_scaled_send_is_two_key(make_gov, clock):
    """INV-GOV-2 "scaled outreach": a send.stage batch above the threshold requires the
    deliverability check on top of the token; a small batch is plain RED."""
    gov, _ = make_gov()
    big = gov.grant("send.stage", "v1", 3600.0)
    action = Action("send.stage", venture_id="v1", params={"count": 30})
    assert not gov.authorize(action, big).ok  # token alone insufficient
    action_checked = Action("send.stage", venture_id="v1", params={"count": 30},
                            check=CheckResult("deliverability", True))
    assert gov.authorize(action_checked, big).ok

    small = gov.grant("send.stage", "v1", 3600.0)
    assert gov.authorize(Action("send.stage", venture_id="v1", params={"count": 5}), small).ok


def test_scaled_send_malformed_count_fails_closed(make_gov):
    """INV-GOV-2 fail closed: a send.stage ``count`` that is not a clean number cannot dodge
    the scaled two-key gate — a malformed count classifies two-key, and authorize refuses it
    (a denial, never an exception) even with a token and a passing check; a negative count is
    likewise refused. The founder's grant survives the failed preconditions unconsumed."""
    gov, _ = make_gov()
    auth = gov.classify(Action("send.stage", venture_id="v1", params={"count": "26"}))
    assert (auth.color, auth.two_key) == (ActionColor.RED, True)

    tok = gov.grant("send.stage", "v1", 3600.0)
    bare = gov.authorize(Action("send.stage", venture_id="v1", params={"count": "26"}), tok)
    assert not bare.ok and bare.reason
    checked = gov.authorize(
        Action("send.stage", venture_id="v1", params={"count": "26"},
               check=CheckResult("deliverability", True)),
        tok,
    )
    assert not checked.ok and checked.reason
    negative = gov.authorize(
        Action("send.stage", venture_id="v1", params={"count": -5}), tok
    )
    assert not negative.ok and negative.reason

    assert gov.authorize(Action("send.stage", venture_id="v1", params={"count": 5}), tok).ok


# --- spend envelope (INV-GOV-4) --------------------------------------------------------------


def test_envelope_within_cap_yellow(make_gov):
    """INV-GOV-4 (R-ENVELOPE): open $120 once (RED); within-cap spends are YELLOW and each
    appends spend_meter{amount_usd, running_total}; the envelope token is single-use (it
    authorized the spend_envelope event and is refused elsewhere)."""
    gov, ledger = make_gov()
    env_token = gov.envelope_open("v1", 120.0)
    assert env_token.cap_usd == 120.0

    envelopes = list(ledger.read(EventFilter(type=EventType.SPEND_ENVELOPE, venture_id="v1")))
    assert len(envelopes) == 1
    assert envelopes[0].payload == {"cap_usd": 120.0}
    assert envelopes[0].authorization == env_token.id

    r1 = gov.spend("v1", 50.0)
    r2 = gov.spend("v1", 40.0)
    assert r1.ok and r1.color is ActionColor.YELLOW and r1.running_total == pytest.approx(50.0)
    assert r2.ok and r2.color is ActionColor.YELLOW and r2.running_total == pytest.approx(90.0)
    assert not r1.degrade and not r2.degrade  # 75% of cap: not yet degraded

    meters = list(ledger.read(EventFilter(type=EventType.SPEND_METER, venture_id="v1")))
    assert [m.payload["amount_usd"] for m in meters] == [50.0, 40.0]
    assert [m.payload["running_total"] for m in meters] == [50.0, 90.0]

    # The envelope token is consumed by the open — not reusable as an authorization.
    assert not gov.authorize(Action("spend.envelope", venture_id="v1"), env_token).ok


def test_envelope_degrade_past_80pct(make_gov):
    """docs/14 auto-degrade: a spend that takes the running total past 80% of cap returns
    degrade=True (the budget-pressure signal), while still ok/YELLOW."""
    gov, _ = make_gov()
    gov.envelope_open("v1", 120.0)
    assert not gov.spend("v1", 90.0).degrade  # 75%
    result = gov.spend("v1", 10.0)  # 100/120 = 83.3%
    assert result.ok and result.degrade


def test_envelope_breach_re_red(make_gov):
    """INV-GOV-4 breach→re-RED: a spend past cap is refused and appends spend_breach
    {attempted, cap}; remaining headroom stays spendable; a FRESH envelope_open (the re-RED)
    resets cap and total and spending resumes."""
    gov, ledger = make_gov()
    gov.envelope_open("v1", 120.0)
    assert gov.spend("v1", 100.0).ok

    breach = gov.spend("v1", 30.0)  # would be 130 > 120
    assert not breach.ok
    assert breach.running_total == pytest.approx(100.0)  # refusal leaves the total unchanged
    assert "RED" in breach.reason  # the re-RED requirement is named
    breaches = list(ledger.read(EventFilter(type=EventType.SPEND_BREACH, venture_id="v1")))
    assert len(breaches) == 1
    assert breaches[0].payload == {"attempted": 130.0, "cap": 120.0}

    assert gov.spend("v1", 15.0).ok  # headroom under the still-open envelope

    gov.envelope_open("v1", 200.0)  # the re-RED
    fresh = gov.spend("v1", 150.0)
    assert fresh.ok and fresh.running_total == pytest.approx(150.0)


def test_spend_without_envelope_refused(make_gov):
    """INV-GOV-4 authorize-once: spending with no envelope ever opened is refused and appends
    nothing (there is no cap to meter against)."""
    gov, ledger = make_gov()
    result = gov.spend("v1", 5.0)
    assert not result.ok and result.cap_usd is None
    assert list(ledger.read()) == []


def test_envelope_state_survives_restart(make_gov, tmp_path, clock):
    """Ledger-as-truth (governance/RISKS R3): a second Gov over the same ledger dir sees the
    same cap/total — accounting is derived from events, never from process memory."""
    gov1, _ = make_gov()
    gov1.envelope_open("v1", 120.0)
    assert gov1.spend("v1", 50.0).ok

    ledger2 = Ledger(tmp_path / "ledger")  # same dir as the fixture's ledger
    gov2 = Gov(ledger2, sup.FakeConfig(), clock=clock)
    assert not gov2.spend("v1", 80.0).ok  # 50 + 80 = 130 > 120
    resumed = gov2.spend("v1", 60.0)  # 50 + 60 = 110 ≤ 120
    assert resumed.ok and resumed.running_total == pytest.approx(110.0)


# --- founder-wide send budget (INV-GOV-5) ----------------------------------------------------


def test_send_budget_founder_wide(make_gov, clock):
    """INV-GOV-5 (R-SEND-BUDGET): one daily budget across ALL ventures — batches from three
    ventures draw down the same 40; the batch that would exceed the remainder is denied
    (never per-venture-unbounded)."""
    gov, ledger = make_gov(send_daily=40)
    assert gov.send_budget_remaining(sup.DAY0) == 40
    assert record_send(gov, ledger, clock, "v1", 15).ok
    assert record_send(gov, ledger, clock, "v2", 15).ok
    assert gov.send_budget_remaining(sup.DAY0) == 10
    assert record_send(gov, ledger, clock, "v3", 10).ok
    assert gov.send_budget_remaining(sup.DAY0) == 0

    denied = record_send(gov, ledger, clock, "v1", 1)
    assert not denied.ok and denied.reason


def test_send_budget_day_rollover(make_gov, clock):
    """INV-GOV-5: the budget is per-day — a new day restores send_daily; remaining is floored
    at 0."""
    gov, ledger = make_gov(send_daily=40)
    assert record_send(gov, ledger, clock, "v1", 40).ok  # scaled → two-key path in the helper
    assert gov.send_budget_remaining(sup.DAY0) == 0

    clock.advance_days(1)
    assert gov.send_budget_remaining(sup.DAY1) == 40
    assert record_send(gov, ledger, clock, "v1", 5).ok
    assert gov.send_budget_remaining(sup.DAY1) == 35
    assert gov.send_budget_remaining(sup.DAY0) == 0


# --- override logging (INV-GOV-6) ------------------------------------------------------------


def test_override_logged_with_reason(make_gov):
    """INV-GOV-6 (R-OVERRIDE-LOG): admission/advance/kill overrides append override{...} with
    the reason; a score override appends score_override{old_score, new_score, reason}."""
    gov, ledger = make_gov()
    gov.record_override("admission", recommendation="park", decision="admit",
                        reason="founder gut: trade contact", venture_id="v1")
    events = list(ledger.read(EventFilter(type=EventType.OVERRIDE, venture_id="v1")))
    assert len(events) == 1
    assert events[0].payload == {"recommendation": "park", "decision": "admit",
                                 "reason": "founder gut: trade contact"}
    assert events[0].actor == "founder"

    gov.record_override("score", recommendation="17", decision="18", reason="warm intro",
                        venture_id="v1", old_score=17, new_score=18)
    scored = list(ledger.read(EventFilter(type=EventType.SCORE_OVERRIDE, venture_id="v1")))
    assert len(scored) == 1
    assert scored[0].payload == {"old_score": 17, "new_score": 18, "reason": "warm intro"}


def test_override_empty_reason_refused(make_gov):
    """INV-GOV-6 fail-closed: an empty or whitespace-only reason raises MissingReason and
    appends nothing."""
    gov, ledger = make_gov()
    for bad in ("", "   "):
        with pytest.raises(MissingReason):
            gov.record_override("kill", recommendation="kill", decision="keep",
                                reason=bad, venture_id="v1")
    assert list(ledger.read()) == []


# --- property: seeded scripts vs the independent oracle --------------------------------------


@pytest.mark.parametrize("seed", range(40))
def test_property_governance_oracle(make_gov, clock, seed):
    """Property (INV-GOV-1/3/4): for seeded random scripts of grants, authorize attempts
    (live/forged/reused/missing tokens), envelope opens, spends, and clock jumps — every Gov
    decision matches the independent GovOracle, and per-envelope metered totals never exceed
    the cap."""
    gov, ledger = make_gov(subdir=f"ledger-{seed}")
    oracle = sup.GovOracle(clock)
    granted: dict[str, list[Token]] = {"v1": [], "v2": [], "v3": []}
    consumed: list[Token] = []

    for i, op in enumerate(sup.governance_script(seed)):
        if op[0] == "grant":
            _, v, ttl = op
            tok = gov.grant("kill", v, ttl)
            oracle.on_grant(tok)
            granted[v].append(tok)
        elif op[0] == "authorize":
            _, v, pick = op
            if pick == "latest":
                tok = granted[v][-1] if granted[v] else None
            elif pick == "reused":
                tok = consumed[-1] if consumed else None
            elif pick == "forged":
                tok = Token(id=f"forged-{seed}-{i}", scope="kill", venture_id=v,
                            issued_at=clock(), expires_at=clock() + 999.0)
            else:
                tok = None
            expected = oracle.expect_authorize("kill", v, tok)
            decision = gov.authorize(Action("kill", venture_id=v), tok)
            assert decision.ok == expected, f"seed {seed} op {i}: {op} -> {decision}"
            if decision.ok:
                oracle.on_authorized(tok)
                consumed.append(tok)
        elif op[0] == "open":
            _, v, cap = op
            gov.envelope_open(v, cap)
            oracle.on_envelope_open(v, cap)
        elif op[0] == "spend":
            _, v, amount = op
            exp_ok, exp_total, exp_degrade = oracle.expect_spend(v, amount)
            result = gov.spend(v, amount)
            assert result.ok == exp_ok, f"seed {seed} op {i}: {op} -> {result}"
            assert result.running_total == pytest.approx(exp_total)
            if result.ok:
                assert result.degrade == exp_degrade
        else:  # advance
            clock.advance(op[1])

    # Cross-check the books against the ledger itself: per venture, metered spends since the
    # latest envelope never exceed its cap.
    for v in ("v1", "v2", "v3"):
        expected_env = oracle.envelope(v)
        events = list(ledger.read(EventFilter(venture_id=v)))
        cap = total = None
        for e in events:
            if e.type is EventType.SPEND_ENVELOPE:
                cap, total = e.payload["cap_usd"], 0.0
            elif e.type is EventType.SPEND_METER:
                total += e.payload["amount_usd"]
        if expected_env is None:
            assert cap is None
        else:
            assert (cap, total) == (pytest.approx(expected_env[0]), pytest.approx(expected_env[1]))
            assert total <= cap + 1e-9
