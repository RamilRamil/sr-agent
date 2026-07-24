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
