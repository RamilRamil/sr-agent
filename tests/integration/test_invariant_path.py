"""Feature 035 T009 — the invariant path end-to-end through a FAKE sandbox.

Drives `_process_finding` with a scripted model + scripted forge output: no live model, no live
engine, no network, no target material. Asserts the distinct `invariant_result` event (FR-007),
that the assertion path is untouched without the flag (FR-009), and that a verified-by-invariant
result is produced only by the deterministic gates (FR-012).
"""
from __future__ import annotations

import types
from pathlib import Path

import scripts.poc_queue_runner as pqr
from sr_agent.eval.tracer import NOOP_TRACER
from sr_agent.packs.audit.tools.write_execute import TestResult as _ForgeResult

TASK = {"id": "X-01", "title": "t", "location": "Vault.redeem", "description": "redeem miscounts",
        "fix": None}
REAL = "contract PoC is Base { function test_x() public { assertEq(uint256(1), 1); } }"
_PASS = _ForgeResult(passed=True, exit_code=0, stdout="Ran 1 test\n[PASS] test_x()", stderr="")

# Scripted forge output for the invariant runs.
_HONEST_HOLDS = "[PASS] invariant_p() (runs: 100, calls: 10000, reverts: 3)\n act_redeem(uint256)\n"
_ADV_BREAKS = ("[FAIL: assertion failed] invariant_p() (runs: 2, calls: 5, reverts: 0)\n"
               "Failing sequence:\n calldata=act_redeem(uint256)\n gap=9500\n")


def _args(project: Path, invariants: bool) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        project=project, test_scaffold="", no_scaffold=True, no_example=True, example_poc="",
        no_file_map=False, lookup_budget=0, attempts=1, image=None, no_scaffold_synthesis=True,
        invariants=invariants,
    )


def _drive(tmp_path, monkeypatch, *, invariants, forge_script,
           callable_api="function redeem(uint256) external"):
    (tmp_path / "audit" / "poc").mkdir(parents=True, exist_ok=True)
    q = list(forge_script)
    monkeypatch.setattr(pqr, "draft", lambda *a, **k: REAL)
    monkeypatch.setattr(pqr, "fix", lambda *a, **k: REAL)
    monkeypatch.setattr(pqr, "run_tests", lambda *a, **k: q.pop(0) if q else _PASS)
    # grounded API — the default carries a legitimate entrypoint so derive_actions finds one
    monkeypatch.setattr(pqr, "build_callable_api", lambda *a, **k: callable_api)
    monkeypatch.setattr(pqr, "read_scaffold", lambda *a, **k: "contract BaseT { function setUp() public {} }")
    monkeypatch.setattr(pqr, "author_invariant",
                        lambda *a, **k: "function invariant_p() public { assertLe(gap, TOL); }")
    events: list[dict] = []
    outcome = pqr._process_finding(
        TASK, args=_args(tmp_path, invariants), client=object(), sandbox=object(),
        log=events.append, symbol_index=None, file_map="", protocol_mode="marker",
        fork_rpc=None, require_pass_effective=False, poc_dir=tmp_path / "audit" / "poc",
        tracer=NOOP_TRACER,
    )
    return outcome, events


def test_without_the_flag_the_assertion_path_is_untouched(tmp_path, monkeypatch):
    """FR-009: opt-in. No flag → no invariant event at all, and the assertion outcome stands."""
    outcome, events = _drive(tmp_path, monkeypatch, invariants=False, forge_script=[_PASS])
    assert not [e for e in events if e["event"] == "invariant_result"]
    assert not any("invariant_outcome" in e for e in events if e["event"] == "task_done")
    assert outcome  # the assertion path still returns its own verdict


def test_invariant_verified_emitted_on_its_own_axis(tmp_path, monkeypatch):
    """FR-007/SC-005: honest HOLDS, adversarial breaks and re-confirms, mechanism matches
    (the finding names `redeem`, the counterexample calls it) → invariant_verified, reported as a
    DISTINCT event and a separate field on task_done — never merged into the assertion outcome."""
    script = [_PASS,                                            # the drafted PoC's own run
              _ForgeResult(passed=True, exit_code=0, stdout=_HONEST_HOLDS, stderr=""),   # honest
              _ForgeResult(passed=False, exit_code=1, stdout=_ADV_BREAKS, stderr=""),    # adversarial
              _ForgeResult(passed=False, exit_code=1, stdout=_ADV_BREAKS, stderr="")]    # re-confirm
    _outcome, events = _drive(tmp_path, monkeypatch, invariants=True, forge_script=script)
    inv = [e for e in events if e["event"] == "invariant_result"]
    assert len(inv) == 1
    assert inv[0]["outcome"] == "invariant_verified"
    done = [e for e in events if e["event"] == "task_done"][0]
    assert done["invariant_outcome"] == "invariant_verified"
    assert done["outcome"] != "invariant_verified"      # axes never merged (FR-008)


def test_honest_violation_without_materiality_is_over_strict(tmp_path, monkeypatch):
    """FR-019/FR-020 end-to-end: the honest run VIOLATES, but the gap does not accumulate across
    budgets → not material → over_strict, never promoted (the reviewer's counterexample)."""
    bounded = ("[FAIL: assertion failed] invariant_p() (runs: 1, calls: 1, reverts: 0)\n"
               " calldata=act_redeem(uint256)\n gap=1\n")
    script = [_PASS,
              _ForgeResult(passed=False, exit_code=1, stdout=bounded, stderr=""),   # honest breaks
              _ForgeResult(passed=False, exit_code=1, stdout=bounded, stderr="")]   # larger budget: same gap
    _outcome, events = _drive(tmp_path, monkeypatch, invariants=True, forge_script=script)
    inv = [e for e in events if e["event"] == "invariant_result"][0]
    assert inv["outcome"] == "invariant_over_strict"
    assert inv.get("material") is False


def test_no_honest_entrypoints_is_unavailable_not_a_pass(tmp_path, monkeypatch):
    """No legitimate entrypoint in the grounded API → the honest side would be vacuous, so the
    path reports unavailable rather than running a one-sided (and therefore untrustworthy) check."""
    outcome, events = _drive(tmp_path, monkeypatch, invariants=True, forge_script=[_PASS],
                             callable_api="function sweep(address) external")
    inv = [e for e in events if e["event"] == "invariant_result"][0]
    assert inv["outcome"] == "invariant_unavailable" and inv["reason"] == "no_honest_entrypoints"


def test_bounded_calibration_overlap(tmp_path, monkeypatch):
    """T014/FR-010b/SC-009: a finding that HAS a report fix and was verified by the assertion
    oracle still runs the invariant path — but only while the small overlap budget lasts — and the
    two verdicts are compared in an `oracle_calibration` event."""
    task = dict(TASK, fix="--- a/x\n+++ b/x\n")
    script = [_PASS,
              _ForgeResult(passed=True, exit_code=0, stdout=_HONEST_HOLDS, stderr=""),
              _ForgeResult(passed=False, exit_code=1, stdout=_ADV_BREAKS, stderr=""),
              _ForgeResult(passed=False, exit_code=1, stdout=_ADV_BREAKS, stderr="")]
    q = list(script)
    (tmp_path / "audit" / "poc").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pqr, "draft", lambda *a, **k: REAL)
    monkeypatch.setattr(pqr, "run_tests", lambda *a, **k: q.pop(0) if q else _PASS)
    monkeypatch.setattr(pqr, "build_callable_api", lambda *a, **k: "function redeem(uint256) external")
    monkeypatch.setattr(pqr, "read_scaffold", lambda *a, **k: "contract BaseT { function setUp() public {} }")
    monkeypatch.setattr(pqr, "author_invariant", lambda *a, **k: "function invariant_p() public { assertLe(g, T); }")
    monkeypatch.setattr(pqr, "mutation_verify", lambda *a, **k: ("verified", ""))
    # structurally-real PoC (the vacuity gate is not what this test is about) so the assertion
    # path actually reaches passed_verified — which is the precondition for calibrating at all
    monkeypatch.setattr(pqr, "_poc_defects", lambda *a, **k: [])
    args = _args(tmp_path, invariants=True)
    args.invariant_overlap_left = 1
    events: list[dict] = []
    pqr._process_finding(task, args=args, client=object(), sandbox=object(), log=events.append,
                         symbol_index=None, file_map="", protocol_mode="marker", fork_rpc=None,
                         require_pass_effective=True, poc_dir=tmp_path / "audit" / "poc",
                         tracer=NOOP_TRACER)
    cal = [e for e in events if e["event"] == "oracle_calibration"]
    assert len(cal) == 1 and "agree" in cal[0]
    assert cal[0]["invariant_verdict"] == "invariant_verified"
    assert args.invariant_overlap_left == 0        # budget consumed, never unbounded


def test_operator_supplied_invariant_base_is_used(tmp_path, monkeypatch):
    """Phase E: the harness base is an OPERATOR input. The per-finding drafting scaffold is often
    absent on real targets, and guessing it emits a harness naming a contract that does not exist."""
    base_dir = tmp_path / "audit" / "level0"
    base_dir.mkdir(parents=True)
    (base_dir / "MyBase.sol").write_text("contract MyBase { function setUp() public virtual {} }")
    seen = {}
    real_build = pqr.build_invariant_harness
    monkeypatch.setattr(pqr, "build_invariant_harness",
                        lambda **kw: seen.update(kw) or real_build(**kw))
    args = _args(tmp_path, invariants=True)
    args.invariant_base = "audit/level0/MyBase.sol:MyBase"   # explicit contract, never inferred
    monkeypatch.setattr(pqr, "read_scaffold", lambda *a, **k: "")     # no drafting scaffold at all
    monkeypatch.setattr(pqr, "draft", lambda *a, **k: REAL)
    monkeypatch.setattr(pqr, "run_tests", lambda *a, **k: _PASS)
    monkeypatch.setattr(pqr, "build_callable_api", lambda *a, **k: "function redeem(uint256) external")
    monkeypatch.setattr(pqr, "author_invariant", lambda *a, **k: "function invariant_p() public {}")
    (tmp_path / "audit" / "poc").mkdir(parents=True, exist_ok=True)
    pqr._process_finding(TASK, args=args, client=object(), sandbox=object(), log=[].append,
                         symbol_index=None, file_map="", protocol_mode="marker", fork_rpc=None,
                         require_pass_effective=False, poc_dir=tmp_path / "audit" / "poc",
                         tracer=NOOP_TRACER)
    assert seen["base_contract"] == "MyBase"
    assert seen["base_import"].endswith("level0/MyBase.sol")
