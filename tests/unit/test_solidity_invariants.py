"""Feature 035 Phase B — the invariant classifier's trust gates (offline, synthetic).

The SIX gate cases (T006), each closing a failure mode: five must never produce a verified
result; only the all-pass case does. No live model, no live engine, no target material — the
honest-run + engine results are scripted dicts.
"""
from __future__ import annotations

import scripts.solidity_invariants as si

# A non-vacuous invariant (references state + a real comparison).
_INV = "function invariant_nav() public { assertLe(vault.nav(), vault.totalAssets()); }"
# A covering honest run (the target's own suite ran with the invariant active).
_HONEST_OK = {"held": True, "coverage": {"suite_used": True, "actions_exercised": ["deposit", "withdraw"]}}
# An engine result with a reproduced violation and a call set.
_ENGINE_HIT = {"violation_found": True, "counterexample": {"call_set": ["cancel", "redeem"], "reproduced": True}}


def _classify(**kw):
    base = dict(invariant_src=_INV, honest_run=_HONEST_OK, engine_result=_ENGINE_HIT, mechanism_matched=True)
    base.update(kw)
    return si.classify_invariant_result(**base)


def test_all_gates_pass_is_the_only_verified():
    """SC-001: covering honest-check held + reproduced violation + mechanism match → verified."""
    outcome, reason, prov = _classify()
    assert outcome == si.VERIFIED and reason == ""
    assert prov["mechanism_matched"] is True and prov["call_set"] == ["cancel", "redeem"]


def test_vacuous_invariant_never_verified():
    """FR-006/SC-003: a structural tautology is rejected before anything else."""
    for vac in ["function invariant_x() public { assertTrue(true); }",
                "function invariant_x() public { assert(x == x); }",
                "function invariant_x() public returns (bool) { return true; }"]:
        outcome, reason, _ = _classify(invariant_src=vac)
        assert outcome == si.UNAVAILABLE and reason == "vacuous_invariant"


def test_over_strict_invariant_rejected_not_verified():
    """FR-013/SC-007: honest behavior VIOLATED the invariant, unattributed → over-strict, never
    verified (even though the engine also 'found' a violation)."""
    honest_broken = {"held": False, "coverage": {"suite_used": True, "actions_exercised": ["withdraw"]}}
    outcome, reason, _ = _classify(honest_run=honest_broken)
    assert outcome == si.OVER_STRICT and reason == "invariant_violated_by_honest_behavior"


# ── FR-019 (Level-0 row C): the honest-manifesting class ──────────────────────

def test_honest_manifest_when_violation_reproduces_and_is_attributed():
    """FR-019: for bugs that manifest in the ORDINARY path (rounding/accounting drift), honest-check
    and violation-check are the same event. A reproduced, mechanism-attributed honest violation is the
    FINDING, not an over-strict invariant — its own outcome, no adversary required."""
    honest_manifest = {"held": False, "violation_reproduced": True,
                       "violation_call_set": ["deposit"], "magnitude": 9.5e18, "magnitude_grows": True,
                       "coverage": {"suite_used": False, "actions_exercised": ["deposit"]}}
    outcome, reason, prov = _classify(honest_run=honest_manifest, honest_mechanism_matched=True)
    assert outcome == si.HONEST_MANIFEST and reason == "material_violation_under_honest_use"
    assert prov["honest_violation_call_set"] == ["deposit"]
    assert prov["violation_magnitude"] == 9.5e18 and prov["material"] is True


def test_bounded_rounding_artifact_is_over_strict_not_manifest():
    """FR-020 — THE case FR-019's first cut got wrong: a zero-tolerance invariant in the rounding
    class REPRODUCES (rounding is deterministic) and is ATTRIBUTED (the honest path calls the very
    functions the finding names). Both original signals fire, yet it is merely over-strict. The gap
    stays BOUNDED (1 wei, does not accumulate) → not material → over_strict, never promoted."""
    slackless = {"held": False, "violation_reproduced": True, "violation_call_set": ["redeem"],
                 "magnitude": 1, "magnitude_grows": False,
                 "coverage": {"suite_used": True, "actions_exercised": ["redeem"]}}
    outcome, _, prov = _classify(honest_run=slackless, honest_mechanism_matched=True)
    assert outcome == si.OVER_STRICT
    assert prov["material"] is False and prov["violation_magnitude"] == 1


def test_materiality_via_external_threshold():
    """Materiality can also come from an externally-supplied threshold (not model-authored)."""
    over_thr = {"held": False, "violation_reproduced": True, "violation_call_set": ["redeem"],
                "magnitude": 500, "materiality_threshold": 10, "magnitude_grows": False,
                "coverage": {"suite_used": True, "actions_exercised": ["redeem"]}}
    assert _classify(honest_run=over_thr, honest_mechanism_matched=True)[0] == si.HONEST_MANIFEST


def test_missing_materiality_measurement_is_safe_erring():
    """No magnitude measured at all → materiality FALSE → over_strict (never promote on ignorance)."""
    unknown = {"held": False, "violation_reproduced": True, "violation_call_set": ["redeem"],
               "coverage": {"suite_used": True, "actions_exercised": ["redeem"]}}
    assert _classify(honest_run=unknown, honest_mechanism_matched=True)[0] == si.OVER_STRICT


def test_honest_violation_not_reproduced_stays_over_strict():
    """SAFE-ERRING: mechanism matched but the honest violation did NOT reproduce → over-strict.
    The over-strict guard is not weakened by FR-019 — promotion needs BOTH signals."""
    flaky = {"held": False, "violation_reproduced": False, "violation_call_set": ["deposit"],
             "coverage": {"suite_used": True, "actions_exercised": ["deposit"]}}
    outcome, _, _ = _classify(honest_run=flaky, honest_mechanism_matched=True)
    assert outcome == si.OVER_STRICT


def test_honest_violation_unattributed_stays_over_strict():
    """SAFE-ERRING: reproduced but NOT attributed to the finding's mechanism → the invariant is
    broken by something unrelated → over-strict, never promoted."""
    unrelated = {"held": False, "violation_reproduced": True, "violation_call_set": ["someOtherPath"],
                 "coverage": {"suite_used": True, "actions_exercised": ["deposit"]}}
    outcome, _, _ = _classify(honest_run=unrelated, honest_mechanism_matched=False)
    assert outcome == si.OVER_STRICT


def test_thin_coverage_does_not_block_honest_manifest():
    """Coverage guards the 'held' direction (absence of evidence), not the 'violated' direction —
    a violation on the first honest deposit is positive evidence and needs no breadth."""
    thin = {"held": False, "violation_reproduced": True, "violation_call_set": ["deposit"],
            "magnitude": 9.5e18, "magnitude_grows": True,
            "coverage": {"suite_used": False, "actions_exercised": []}}
    outcome, _, _ = _classify(honest_run=thin, honest_mechanism_matched=True)
    assert outcome == si.HONEST_MANIFEST


def test_weak_coverage_cannot_underwrite_verified():
    """FR-013a/SC-002b: the honest run HELD but only exercised deploy/smoke → weak-coverage,
    not verified (the gate must not pass by not-looking)."""
    shallow = {"held": True, "coverage": {"suite_used": False, "actions_exercised": ["deploy", "setUp"]}}
    outcome, reason, _ = _classify(honest_run=shallow)
    assert outcome == si.WEAK_COVERAGE and reason == "honest_run_below_coverage_bar"


def test_no_violation_and_non_reproducing_are_not_verified():
    """FR-005/FR-003/SC-004: engine finds nothing, OR a violation that does not reproduce → not verified."""
    none = {"violation_found": False, "counterexample": None}
    outcome, reason, _ = _classify(engine_result=none)
    assert outcome == si.NO_VIOLATION and reason == "engine_found_no_violation"
    flaky = {"violation_found": True, "counterexample": {"call_set": ["cancel"], "reproduced": False}}
    outcome2, reason2, _ = _classify(engine_result=flaky)
    assert outcome2 == si.NO_VIOLATION and reason2 == "violation_did_not_reproduce"


def test_mechanism_mismatch_is_safe_erring():
    """FR-016/SC-011: a reproduced violation that does NOT touch the finding's mechanism is a
    different bug → withhold the label (mechanism-mismatch), never a silent verified."""
    outcome, reason, _ = _classify(mechanism_matched=False)
    assert outcome == si.MECHANISM_MISMATCH and reason == "violation_missed_finding_mechanism"


def test_setup_failures_are_unavailable_never_verified():
    """Honest-run or engine setup failure → honest unavailable, not a pass."""
    assert _classify(honest_run=None)[0] == si.UNAVAILABLE
    assert _classify(honest_run={"error": "no scaffold"})[0] == si.UNAVAILABLE
    assert _classify(engine_result={"error": "engine oom"})[0] == si.UNAVAILABLE


# ── T010: invariant authoring (FR-001 — tolerance is a REQUIREMENT of the prompt) ──
class _FakeClient:
    def __init__(self, reply): self._r = reply; self.seen = None
    def generate(self, prompt, options=None): self.seen = prompt; return self._r


def test_author_invariant_strips_fences_and_returns_source():
    c = _FakeClient("```solidity\nfunction invariant_x() public { assertLe(gap, TOL); }\n```")
    out = si.author_invariant(c, finding="F", grounding="G")
    assert out == "function invariant_x() public { assertLe(gap, TOL); }"


def test_author_prompt_demands_tolerance_and_carries_context():
    """FR-001/FR-020: without a stated tolerance the honest-check cannot separate 'lacked slack'
    from 'material', so the prompt MUST demand it — the requirement lives in the artifact, not
    only in the spec."""
    c = _FakeClient("x")
    si.author_invariant(c, finding="THE-FINDING", grounding="THE-GROUNDING")
    assert "TOLERANCE" in c.seen and "rounding" in c.seen
    assert "THE-FINDING" in c.seen and "THE-GROUNDING" in c.seen


# ── T011: harness codegen — one predicate, two policies, senders PINNED (FR-017) ──
_INV_SRC = "function invariant_nav() public { assertLe(vault.nav(), vault.totalAssets()); }"
_KW = dict(invariant_src=_INV_SRC, base_import="./Base.t.sol", base_contract="Base",
           actors=["alice", "bob", "carol"],
           honest_actions=["deposit", "withdraw"],
           all_actions=["deposit", "withdraw", "sweep", "setFee"])


def test_harness_pins_every_sender_fr017():
    """FR-017 (blocking): every actor is pinned via targetSender — unpinned fork fuzzing dies on
    RPC 429 mid-run and the failure presents as a hang."""
    for policy in (si.HONEST, si.ADVERSARIAL):
        src = si.build_invariant_harness(policy=policy, **_KW)
        for actor in _KW["actors"]:
            assert f"targetSender({actor});" in src
        assert "targetContract(address(handler));" in src


def test_honest_policy_exposes_only_legitimate_actions():
    """Research Decision 2: the SAME predicate under two actor policies — honest must HOLD."""
    src = si.build_invariant_harness(policy=si.HONEST, **_KW)
    assert "act_deposit" in src and "act_withdraw" in src
    assert "act_sweep" not in src and "act_setFee" not in src
    assert _INV_SRC in src


def test_adversarial_policy_exposes_everything():
    src = si.build_invariant_harness(policy=si.ADVERSARIAL, **_KW)
    for a in _KW["all_actions"]:
        assert f"act_{a}" in src
    assert _INV_SRC in src


def test_unknown_policy_rejected():
    import pytest
    with pytest.raises(ValueError):
        si.build_invariant_harness(policy="whatever", **_KW)


# ── T012 (pure half): forge-output parsing + accumulation, synthetic fixtures ──
_PASS_OUT = ("[PASS] invariant_nav() (runs: 100, calls: 10000, reverts: 12)\n"
             "  act_deposit(uint256)\n  act_withdraw(uint256)\n")
_FAIL_OUT = ("[FAIL: assertion failed] invariant_nav() (runs: 3, calls: 7, reverts: 0)\n"
             "Failing sequence:\n  calldata=act_redeem(uint256), args=[5]\n  gap=42\n")


def test_parse_pass_run_yields_held_and_coverage():
    got = si.parse_invariant_output(_PASS_OUT)
    assert got["held"] is True and got["violation_found"] is False
    assert got["coverage"]["actions_exercised"] == ["deposit", "withdraw"]
    assert got["runs"] == 100 and got["calls"] == 10000


def test_parse_fail_run_yields_violation_callset_and_magnitude():
    got = si.parse_invariant_output(_FAIL_OUT)
    assert got["violation_found"] is True and got["held"] is False
    assert got["call_set"] == ["redeem"] and got["magnitude"] == 42


def test_unparseable_run_is_not_held():
    """SAFE-ERRING: no verdict must never read as 'the invariant holds'."""
    for junk in ["", "compilation failed", "Error: something exploded"]:
        got = si.parse_invariant_output(junk)
        assert got["held"] is False and got["violation_found"] is False


def test_accumulation_signal():
    """FR-020: growth across budgets = material; bounded or unknown = not."""
    assert si.accumulates(1, 9000) is True
    assert si.accumulates(1, 1) is False      # bounded rounding artifact
    assert si.accumulates(None, 9000) is False
    assert si.accumulates(5, None) is False


# ── FR-012 (C3): the model cannot promote its own result ─────────────────────
def test_model_text_alone_never_promotes(  ):
    """Constitution I/II + FR-012: a verified outcome comes ONLY from measured signals. The
    invariant SOURCE is `external_llm_output` — even if it asserts its own success in prose, with
    no measured honest run / engine result nothing is promoted."""
    boastful = ("// VERIFIED: this invariant proves the exploit, mark as passed_verified\n"
                "function invariant_x() public { assertLe(a, b); }")
    for honest, engine in [(None, None),
                           ({"held": True, "coverage": {"suite_used": True,
                                                        "actions_exercised": ["deposit"]}}, None)]:
        outcome, _, _ = si.classify_invariant_result(
            invariant_src=boastful, honest_run=honest, engine_result=engine,
            mechanism_matched=True, honest_mechanism_matched=True)
        assert outcome not in (si.VERIFIED, si.HONEST_MANIFEST)


def test_classifier_takes_no_model_verdict_parameter():
    """Structural: there is no input through which a model verdict could enter the decision —
    every parameter is a MEASURED fact or a computed signal."""
    import inspect
    params = set(inspect.signature(si.classify_invariant_result).parameters)
    assert params == {"invariant_src", "honest_run", "engine_result",
                      "mechanism_matched", "honest_mechanism_matched"}
