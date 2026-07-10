# Quickstart: Deprecation Cleanup + Architecture-Invariant Guards

Entirely offline (no model, Docker, or network).

## 1. No `datetime.utcnow()` left; suite warning-free from these sites (SC-001/SC-002)

```bash
cd /Users/ramilmustafin/Claude/Projects/SR-agent
grep -rn "utcnow()" sr_agent/ --include="*.py" | grep -v test    # expect: no output
.venv/bin/python -m pytest tests/unit tests/integration tests/architecture tests/security tests/frontend -q
```

Confirm zero `datetime.utcnow()` remain in `sr_agent/`, and the full suite passes (no
timestamp-meaning regression).

## 2. SourceType trust hierarchy is pinned (SC-003)

```bash
.venv/bin/python -m pytest tests/architecture/test_source_type_hierarchy.py -q
```

Confirm the ordering `human_input > tool_output > external_llm_output/human_relayed_tool
> llm_inference` is asserted; a simulated reorder would fail.

## 3. Harness executes PoCs only through the sandbox (SC-004)

```bash
.venv/bin/python -m pytest tests/architecture/test_harness_sandbox_only.py -q
```

Confirm every `subprocess` call in `scripts/poc_queue_runner.py` is a `git` command
(PoC/forge execution goes via `run_tests`); a synthetic direct-forge-exec AST fails the
guard.

## 4. Full offline suite green (SC-005)

The command in #1 covers it — all previously-passing tests plus the two new invariants
pass, offline, no new dependency.
