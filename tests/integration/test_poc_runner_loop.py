"""Feature 009 US2: the PoC-workability harness's per-finding orchestration loop,
driven end-to-end OFFLINE — no Ollama, no Docker, no network.

`_process_finding` (extracted from `main()`'s loop body, contracts/
process-finding.md) is driven through a scripted fake model (monkeypatched
`draft`/`fix`) and a fake sandbox (monkeypatched `run_tests` returning scripted
`TestResult`s). Each scenario asserts BOTH the recorded `outcome` and the key
events emitted — so a regression in the loop's control flow or its outcome
classification is caught locally in seconds, not only in a metered GPU run (every
bug this class surfaced in this session's live runs would have been caught here).
"""
from __future__ import annotations

import types
from pathlib import Path

import scripts.poc_queue_runner as pqr
from sr_agent.eval.tracer import NOOP_TRACER
from sr_agent.packs.audit.tools.write_execute import TestResult as _ForgeResult


def _args(project: Path, attempts: int = 3) -> types.SimpleNamespace:
    """A minimal argparse-like namespace: scaffold/example/file-map all disabled
    so the loop's grounding calls are no-ops and the test stays offline and
    focused on the draft→run→fix→classify control flow."""
    return types.SimpleNamespace(
        project=project, test_scaffold="", no_scaffold=True, no_example=True,
        example_poc="", no_file_map=True, lookup_budget=0, attempts=attempts, image=None,
        no_scaffold_synthesis=False,
    )


def _run(task, project, *, drafts, fixes, results, attempts=3, monkeypatch,
         require_pass=False):
    """Drive one finding through `_process_finding` with scripted model + sandbox.
    Returns (outcome, events)."""
    draft_q = list(drafts)
    fix_q = list(fixes)
    result_q = list(results)
    monkeypatch.setattr(pqr, "draft", lambda *a, **k: draft_q.pop(0))
    monkeypatch.setattr(pqr, "fix", lambda *a, **k: fix_q.pop(0))
    monkeypatch.setattr(pqr, "run_tests", lambda *a, **k: result_q.pop(0))

    events: list[dict] = []
    outcome = pqr._process_finding(
        task, args=_args(project, attempts), client=object(), sandbox=object(),
        log=events.append, symbol_index=None, file_map="", protocol_mode="marker",
        fork_rpc=None, require_pass_effective=require_pass, poc_dir=project / "audit" / "poc",
        tracer=NOOP_TRACER,
    )
    return outcome, events


def _evnames(events):
    return [e["event"] for e in events]


TASK = {"id": "X-01", "title": "example finding", "location": "", "description": "a bug"}

# A structurally-real PoC (has an assertion) vs. a vacuous one (no assertion).
REAL = "contract PoC is Base { function test_x() public { assertEq(cdo.coverage(), 1); } }"
VACUOUS = "contract PoC is Base { function test_x() public { /* nothing */ } }"

_PASS = _ForgeResult(passed=True, exit_code=0, stdout="Ran 1 test for X\n[PASS] test_x()", stderr="")
_VACUOUS_PASS = _ForgeResult(passed=True, exit_code=0, stdout="Ran 1 test for X\n[PASS] test_x()", stderr="")
_COMPILE_ERR = _ForgeResult(passed=False, exit_code=1,
                          stdout="Compiler run failed:\nError (7576): Undeclared identifier.", stderr="")


def test_loop_clean_pass(tmp_path, monkeypatch):
    """First draft is structurally real and the run passes → outcome 'passed'."""
    outcome, events = _run(TASK, tmp_path, drafts=[REAL], fixes=[], results=[_PASS], monkeypatch=monkeypatch)
    assert outcome == "passed"
    names = _evnames(events)
    assert names[0] == "task_start"
    assert "tested" in names
    assert events[-1]["event"] == "task_done" and events[-1]["outcome"] == "passed"


def test_loop_vacuous_pass_rejected(tmp_path, monkeypatch):
    """A run that passes but whose PoC is vacuous (no assertion) is NOT a success —
    every attempt is rejected and the finding ends 'vacuous_pass'."""
    outcome, events = _run(
        TASK, tmp_path, drafts=[VACUOUS], fixes=[VACUOUS], results=[_VACUOUS_PASS, _VACUOUS_PASS],
        attempts=2, monkeypatch=monkeypatch,
    )
    assert outcome == "vacuous_pass"
    assert "rejected_vacuous" in _evnames(events)
    assert events[-1]["outcome"] == "vacuous_pass"


def test_loop_compile_error_then_repair(tmp_path, monkeypatch):
    """A draft with a compile error, corrected by the next fix → a repair round runs
    and the corrected attempt reaches 'passed'."""
    outcome, events = _run(
        TASK, tmp_path, drafts=[REAL], fixes=[REAL], results=[_COMPILE_ERR, _PASS],
        attempts=3, monkeypatch=monkeypatch,
    )
    assert outcome == "passed"
    names = _evnames(events)
    assert names.count("written") == 2  # two attempts written
    assert names.count("tested") == 2


def test_loop_stall_exhausts(tmp_path, monkeypatch):
    """Every attempt returns the identical compile error → a stall is detected and
    the finding ends 'exhausted'."""
    outcome, events = _run(
        TASK, tmp_path, drafts=[REAL], fixes=[REAL, REAL],
        results=[_COMPILE_ERR, _COMPILE_ERR, _COMPILE_ERR], attempts=3, monkeypatch=monkeypatch,
    )
    assert outcome == "exhausted"
    assert "stall_detected" in _evnames(events)
    assert events[-1]["outcome"] == "exhausted"


def test_loop_budget_stop(tmp_path, monkeypatch):
    """main()'s wall-clock guard: once the budget is exceeded, the loop stops
    without processing the next finding. Driven through main() with the pre-loop
    seams faked; a scripted monotonic clock trips the budget on the 2nd finding."""
    processed: list[str] = []
    monkeypatch.setattr(pqr, "_process_finding", lambda task, **k: processed.append(task["id"]))

    # scripted monotonic: run_start=0, finding-1 check=0 (under budget),
    # finding-2 check=100s (100/60 > 1 min budget → break).
    clock = iter([0.0, 0.0, 100.0, 100.0, 100.0])
    monkeypatch.setattr(pqr.time, "monotonic", lambda: next(clock))

    fake_tasks = [{"id": "A-01", "title": "a", "location": "", "description": "d"},
                  {"id": "A-02", "title": "b", "location": "", "description": "d"}]
    monkeypatch.setattr(pqr, "extract_tasks", lambda *a, **k: fake_tasks)
    monkeypatch.setattr(pqr, "build_file_manifest", lambda *a, **k: "")
    monkeypatch.setattr(pqr, "DockerSandbox", lambda *a, **k: object())

    class _FakeClient:
        model = "fake"
        def __init__(self, *a, **k): pass
        def warm(self, *a, **k): return True
        def ready(self, *a, **k): return True
        def available(self, *a, **k): return True
        def supports_tools(self, *a, **k): return False
    monkeypatch.setattr(pqr, "LocalClient", _FakeClient)

    monkeypatch.setattr(pqr, "Tracer", lambda *a, **k: NOOP_TRACER)

    report = tmp_path / "report.md"
    report.write_text("# report", encoding="utf-8")
    monkeypatch.setenv("POC_PROJECT", str(tmp_path))
    monkeypatch.setenv("POC_REPORT", str(report))
    monkeypatch.setattr("sys.argv", ["poc_queue_runner.py", "--no-symbol-index",
                                     "--attempts", "1", "--max-minutes", "1"])

    pqr.main()

    # only the first finding was processed before the budget tripped on the second.
    assert processed == ["A-01"]


# ── Feature 010: mutation-verify wiring into the real_pass branch ───────────
# mutation_verify's internals (extract/apply/classify) are unit-tested in
# test_poc_queue_runner.py; here we test that the LOOP consults it exactly on a
# genuine PASS and applies its verdict — verified/unavailable keep `passed`, only
# unverified_pass downgrades.

def _run_with_mutverify(task, project, *, results, verdict, monkeypatch, attempts=2):
    result_q = list(results)
    monkeypatch.setattr(pqr, "draft", lambda *a, **k: REAL)
    monkeypatch.setattr(pqr, "fix", lambda *a, **k: REAL)
    monkeypatch.setattr(pqr, "run_tests", lambda *a, **k: result_q.pop(0))
    calls = {"n": 0}
    def _fake_mutverify(*a, **k):
        calls["n"] += 1
        return verdict
    monkeypatch.setattr(pqr, "mutation_verify", _fake_mutverify)
    events = []
    outcome = pqr._process_finding(
        task, args=_args(project, attempts), client=object(), sandbox=object(),
        log=events.append, symbol_index=None, file_map="", protocol_mode="marker",
        fork_rpc=None, require_pass_effective=False, poc_dir=project / "audit" / "poc",
        tracer=NOOP_TRACER,
    )
    return outcome, events, calls["n"]


def test_loop_mutation_verified_keeps_passed(tmp_path, monkeypatch):
    """A genuine PASS whose PoC then FAILS on the applied fix stays `passed`."""
    task = {"id": "H-01", "title": "silo padding", "location": "", "description": "d", "fix": "DIFF"}
    outcome, events, n = _run_with_mutverify(task, tmp_path, results=[_PASS], verdict="verified", monkeypatch=monkeypatch)
    assert outcome == "passed"
    assert n == 1  # consulted exactly once, on the pass


def test_loop_mutation_unverified_downgrades(tmp_path, monkeypatch):
    """The 2026-07-06 false-positive class: a PASS that STILL passes on the fix is
    downgraded to `unverified_pass`, not reported as success (SC-001)."""
    task = {"id": "H-01", "title": "silo padding", "location": "", "description": "d", "fix": "DIFF"}
    outcome, events, n = _run_with_mutverify(task, tmp_path, results=[_PASS], verdict="unverified_pass", monkeypatch=monkeypatch)
    assert outcome == "unverified_pass"
    assert events[-1]["outcome"] == "unverified_pass"


def test_loop_mutation_unavailable_keeps_passed(tmp_path, monkeypatch):
    """When verification is unavailable (no fix / won't apply), the pass is kept —
    never a false downgrade (SC-003)."""
    task = {"id": "H-01", "title": "silo padding", "location": "", "description": "d", "fix": None}
    outcome, events, n = _run_with_mutverify(task, tmp_path, results=[_PASS], verdict="unavailable", monkeypatch=monkeypatch)
    assert outcome == "passed"


def test_loop_mutation_not_consulted_on_non_pass(tmp_path, monkeypatch):
    """mutation_verify runs ONLY on a genuine pass (FR-007) — a stall/exhausted
    finding never consults it."""
    task = {"id": "H-01", "title": "t", "location": "", "description": "d", "fix": "DIFF"}
    _, _, n = _run_with_mutverify(
        task, tmp_path, results=[_COMPILE_ERR, _COMPILE_ERR], verdict="verified",
        monkeypatch=monkeypatch, attempts=2)
    assert n == 0  # never consulted — the finding never passed


# ── Feature 011: scaffold synthesis wiring into _process_finding ────────────
# synthesize_scaffold's internals are unit-tested; here we test that the loop
# consults it exactly on detected insufficiency and swaps the scaffold on success,
# falls back on failure, and never consults it when the scaffold is sufficient.

def _run_synth(task, project, *, missing, synth_returns, monkeypatch):
    monkeypatch.setattr(pqr, "scaffold_missing_types", lambda *a, **k: missing)
    calls = {"n": 0}
    def _fake_synth(proj, tsk, miss, existing, si, cl, sb, log, **k):
        calls["n"] += 1
        if synth_returns is None:
            log({"event": "scaffold_synthesis_failed", "finding_id": tsk["id"], "reason": "no_build"})
            return None
        # write a real base file so read_scaffold can read it back
        d = project / "audit" / "poc" / "_synth"
        d.mkdir(parents=True, exist_ok=True)
        p = d / "SynthBase.sol"
        p.write_text("// SPDX\npragma solidity ^0.8.28;\nabstract contract SynthBase {}\n", encoding="utf-8")
        log({"event": "scaffold_synthesized", "finding_id": tsk["id"], "path": str(p.relative_to(project))})
        return p
    monkeypatch.setattr(pqr, "synthesize_scaffold", _fake_synth)
    monkeypatch.setattr(pqr, "draft", lambda *a, **k: REAL)
    monkeypatch.setattr(pqr, "run_tests", lambda *a, **k: _PASS)
    monkeypatch.setattr(pqr, "mutation_verify", lambda *a, **k: "unavailable")
    events = []
    outcome = pqr._process_finding(
        task, args=_args(project, 1), client=object(), sandbox=object(),
        log=events.append, symbol_index=None, file_map="", protocol_mode="marker",
        fork_rpc=None, require_pass_effective=False, poc_dir=project / "audit" / "poc",
        tracer=NOOP_TRACER,
    )
    return outcome, events, calls["n"]


def test_loop_synth_used_on_success(tmp_path, monkeypatch):
    """An insufficient-scaffold finding whose synthesis succeeds drafts under the
    synthesized base (a `scaffold_synthesized` grounding swap is emitted)."""
    task = {"id": "H-01", "title": "silo padding", "location": "SharesCooldown", "description": "d"}
    outcome, events, n = _run_synth(task, tmp_path, missing=["SharesCooldown"],
                                    synth_returns="ok", monkeypatch=monkeypatch)
    assert n == 1  # synthesis consulted on insufficiency
    assert any(e["event"] == "scaffold_synthesized" for e in events)
    assert any(e.get("stage") == "synthesized" for e in events)  # scaffold swapped


def test_loop_synth_fallback_on_failure(tmp_path, monkeypatch):
    """Synthesis failure keeps the finding on its prior scaffold and never blocks."""
    task = {"id": "H-01", "title": "t", "location": "SharesCooldown", "description": "d"}
    outcome, events, n = _run_synth(task, tmp_path, missing=["SharesCooldown"],
                                    synth_returns=None, monkeypatch=monkeypatch)
    assert n == 1
    assert any(e["event"] == "scaffold_synthesis_failed" for e in events)
    assert not any(e.get("stage") == "synthesized" for e in events)  # no swap
    assert events[-1]["event"] == "task_done"  # run proceeded, not blocked


def test_loop_synth_skipped_when_sufficient(tmp_path, monkeypatch):
    """A finding whose scaffold is sufficient never consults synthesis (SC-003)."""
    task = {"id": "H-01", "title": "t", "location": "SharesCooldown", "description": "d"}
    outcome, events, n = _run_synth(task, tmp_path, missing=[],  # sufficient
                                    synth_returns="ok", monkeypatch=monkeypatch)
    assert n == 0  # never consulted
    assert not any(e["event"] in ("scaffold_synthesized", "scaffold_synthesis_failed") for e in events)


# ── Feature 012: harness prompt management (identical-off + version recorded) ─

class _PromptSpyClient:
    """Captures the prompt text draft() feeds to generate() (marker mode)."""
    model = "fake"
    def __init__(self):
        self.prompts = []
    def generate(self, prompt, options=None):
        self.prompts.append(prompt)
        return REAL


def test_loop_prompt_identical_when_tracing_off(tmp_path):
    """FR-002/SC-001: with a disabled tracer, draft's assembled prompt equals the
    pre-feature constant-based prompt (the fallback IS the constant)."""
    spy = _PromptSpyClient()
    # the byte-exact reference: format the constants exactly as the old code did
    checklist = pqr.EXPLOIT_QUALITY_CHECKLIST
    reference = pqr.DRAFT_PROMPT.format(
        fid="H-01", title="t", location="", description="d", ident="H_01",
        source="(no contract name found in location)",
        scaffold="(no base provided — deploy the real contracts yourself; still NEVER mock them)",
        example="(none)", files="(none)", callable="(none)",
        exploit_quality_checklist=checklist,
    ) + pqr._LOOKUP_MARKER_SUFFIX
    task = {"id": "H-01", "title": "t", "location": "", "description": "d"}
    pqr.draft(spy, task, tmp_path, protocol_mode="marker", tracer=NOOP_TRACER)
    assert spy.prompts[-1] == reference  # byte-identical to pre-feature behavior


def test_generation_records_prompt_version(tmp_path):
    """SC-002/SC-003: a draft records prompt_provenance (name+version) in the
    generation metadata; a fallback-sourced prompt records version None."""
    class _VerTracer:
        enabled = True
        _client = None
        def __init__(self): self.gen_meta = []
        def get_prompt_versioned(self, name, fallback):
            return (fallback, 3) if name == "poc-draft" else (fallback, None)
        def trace(self, *a, **k):
            import contextlib
            return contextlib.nullcontext(None)
        def generation(self, trace, *, name, model, input, output, usage=None, metadata=None):
            self.gen_meta.append(metadata)
    tr = _VerTracer()
    spy = _PromptSpyClient()
    task = {"id": "H-01", "title": "t", "location": "", "description": "d"}
    pqr.draft(spy, task, tmp_path, protocol_mode="marker", tracer=tr)
    prov = {p["name"]: p["version"] for p in tr.gen_meta[-1]["prompt_provenance"]}
    assert prov["poc-draft"] == 3                     # fetched version recorded
    assert prov["poc-exploit-checklist"] is None      # fallback-sourced → None
    assert prov["poc-lookup-marker"] is None
