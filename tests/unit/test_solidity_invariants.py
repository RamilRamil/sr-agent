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
    """FR-013/SC-007: honest behavior VIOLATED the invariant → over-strict, never verified
    (even though the engine also 'found' a violation)."""
    honest_broken = {"held": False, "coverage": {"suite_used": True, "actions_exercised": ["withdraw"]}}
    outcome, reason, _ = _classify(honest_run=honest_broken)
    assert outcome == si.OVER_STRICT and reason == "invariant_violated_by_honest_behavior"


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
