# Quickstart: Harness Verdict-Logic Test Coverage + Orchestration Integration Test

How to verify this feature is done — entirely offline (no model, Docker, or network).

## 1. Verdict gates and repair helpers are directly tested

```bash
cd /Users/ramilmustafin/Claude/Projects/SR-agent
.venv/bin/python -m pytest tests/unit/test_poc_queue_runner.py -q
```

Confirm there is now a direct test for each of: `_compiled` (positive-signal;
rejects a differently-worded compile failure), `_poc_defects` (empty/mock/no-import),
the stall signature (same error on a shifted line number still detected as a stall),
and each deterministic repair helper (`_targeted_hints`/`_line_level_hints`/
`_sig_by_method`/`_fix_setup_override`/`_fix_import_paths`/`revert_hints`).

## 2. The spec-006 regression can't come back silently (SC-001)

Temporarily re-break `_compiled` to a denylist (`"Compiler run failed" not in blob`)
and confirm a test now fails:

```bash
# (manual check) revert _compiled to the old denylist form, run:
.venv/bin/python -m pytest tests/unit/test_poc_queue_runner.py -k compiled -q
# expect: FAIL — the positive-signal test catches it. Then restore _compiled.
```

## 3. The orchestration loop is covered offline (SC-003)

```bash
.venv/bin/python -m pytest tests/integration/test_poc_runner_loop.py -q
```

Confirm five scenarios pass with no Ollama/Docker/network: a clean pass, a rejected
vacuous pass, a compile-error repair that then succeeds, a stall→exhausted, and a
budget stop. Each asserts both the recorded `outcome` and the emitted event sequence.

## 4. Scaffold sufficiency understands inheritance (SC-004)

```bash
.venv/bin/python -m pytest tests/unit/test_poc_queue_runner.py -k scaffold_missing -q
```

Confirm a scaffold that provides the needed contract only via an inherited parent base
is NOT reported missing, and one that declares nothing of that type anywhere in its
chain IS reported missing. (A real-fixture sanity check against this session's target
project may be included but skipped when that external path is absent.)

## 5. Full offline suite still green (SC-005)

```bash
.venv/bin/python -m pytest tests/unit tests/integration tests/architecture tests/security tests/frontend -q
```

All previously-passing tests plus the new ones pass, entirely offline. No new test
touches a live model, Docker, or any bug-bounty target's code/names/paths (FR-009).
