# Implementation Plan: Harness Verdict-Logic Test Coverage + Orchestration Integration Test

**Branch**: `009-harness-verdict-tests` | **Date**: 2026-07-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/009-harness-verdict-tests/spec.md`

## Summary

Close the harness's biggest test gap: the verdict gates (`_compiled`, `_poc_defects`,
stall signatures) and deterministic repair helpers that decide pass/fail have zero
direct tests, and `main()`'s whole draft→run→fix loop has no integration test. Add
direct offline unit tests for every verdict/repair function (pinning the exact bug
classes from this session), add an offline integration test that drives the
per-finding loop through a scripted fake model + fake sandbox, and re-platform the
regex `scaffold_missing_types` onto the AST-backed `SymbolIndex` so it sees inherited
state variables. All offline; no kernel change.

## Technical Context

**Language/Version**: Python 3.11+ (existing `scripts/`/`tests/` codebase)

**Primary Dependencies**: none new. Tests use pytest + monkeypatch (already the
harness's test style). `SymbolIndex` (spec 007, `scripts/solidity_index.py`) already
present for the US3 re-platform.

**Storage**: N/A — tests write only to `tmp_path`; no persisted state.

**Testing**: pytest, entirely offline. The integration test monkeypatches the
module-level seams already present in `scripts/poc_queue_runner.py`: `extract_tasks`,
`run_tests`, and the `LocalClient` construction — plus a fake sandbox object. No
Ollama, no Docker, no network, no live-run infra of any kind.

**Target Platform**: local dev machine; CI-safe (nothing external).

**Project Type**: single project — extends `scripts/poc_queue_runner.py` (minimal,
behavior-preserving) and its existing test file `tests/unit/test_poc_queue_runner.py`.

**Performance Goals**: the new integration + unit tests complete in well under a
second each (no I/O beyond tmp files) — the whole point is a fast local safety net vs.
a multi-minute metered GPU run.

**Constraints**: MUST NOT change any verdict's actual behavior (tests pin existing
behavior; the only production-code change beyond the US3 re-platform is a
behavior-preserving extraction of the loop body if needed for testability). MUST run
fully offline (FR-009). MUST NOT embed any bug-bounty target's code/names/paths — use
synthetic Solidity fixtures or the project's existing offline fixtures.

**Scale/Scope**: ~one new unit test per verdict gate + repair helper (~8-10 functions),
one integration test module covering 5 outcome paths, and the US3 `SymbolIndex`
re-platform of a single function + its tests. All in the standalone harness's test
surface.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Secure-Kernel Trust Invariants** — PASS. Entirely within the standalone
  harness (`scripts/poc_queue_runner.py`) and its tests; no kernel control-flow,
  `SourceType`, memory-signing, or tool-budget code touched. Adding tests strengthens,
  never weakens, an invariant.
- **II. Human Authority for Privileged & Irreversible Actions** — PASS. No
  privileged/irreversible action added; the fake sandbox is a test double for the
  read-of-forge-output path, and the real sandbox's security invariants are unchanged
  and untested-against here (out of scope).
- **III. Kernel / Capability-Pack Separation** — PASS. No pack boundary touched; the
  US3 re-platform reuses the harness-local `SymbolIndex`, not a kernel primitive.
- **IV. Human-Gated Knowledge Promotion** — PASS. No knowledge writes; tests are pure
  observation.
- **V. No Paid-API Dependency** — PASS. No API involved; tests are offline by
  requirement (FR-009).

This feature is squarely in the spirit of the constitution's "Development Workflow &
Quality Gates" (test-first for verdict-producing behavior) and the eval-robustness
doctrine of [docs/eval-principles.md](../../docs/eval-principles.md). No violations —
Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/009-harness-verdict-tests/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (test-double interface)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
scripts/
├── poc_queue_runner.py   # MINIMAL change: (a) re-platform scaffold_missing_types
│                         #   onto SymbolIndex (US3); (b) IF main()'s per-finding
│                         #   loop can't be driven cleanly via monkeypatched seams,
│                         #   a behavior-preserving extraction of the loop body into
│                         #   a testable `_process_finding(...)` helper (research R1)
│                         #   — same events, same outcomes, no behavior change.
└── solidity_index.py     # possibly a small read-only helper for inherited-var
                          #   resolution (US3) if not already expressible via lookup()

tests/unit/
└── test_poc_queue_runner.py   # EXTENDED: direct unit tests for every verdict gate
                                #   + repair helper (US1); the scaffold-inheritance
                                #   tests (US3)

tests/integration/            # EXISTING dir — add one file here
└── test_poc_runner_loop.py    # NEW: the offline draft→run→fix loop integration
                                #   test (US2) — fake model + fake sandbox
```

**Structure Decision**: Single project. The bulk is new tests. The only production
change is the US3 re-platform (small, mechanical) and — only if required for a clean
integration test — a behavior-preserving extraction of `main()`'s loop body, decided
in research.md R1. The loop-level test lands in the EXISTING `tests/integration/` directory, keeping it distinct from the fast pure-unit tests (both run under the
same offline pytest invocation).

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*

**Post-design re-check (after Phase 0/1)**: research.md's decisions (test through
monkeypatched seams first, extract the loop only if that proves infeasible; reuse
`SymbolIndex` for US3) introduce no new violations — still PASS on all five
principles.
