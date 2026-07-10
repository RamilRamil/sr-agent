# Implementation Plan: Deprecation Cleanup + Architecture-Invariant Guards

**Branch**: `013-cleanup-invariants` | **Date**: 2026-07-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/013-cleanup-invariants/spec.md`

## Summary

Pure hardening, roadmap item 5. Replace the 6 deprecated `datetime.utcnow()` calls
(kernel/pack) with the timezone-aware `datetime.now(timezone.utc)` — same instant, no
behavior change (verified: no test pins a timestamp's string shape) — and add two
architecture-invariant tests: the SourceType trust-hierarchy ordering (Principle I) and
that the PoC harness executes PoC/forge code only through the sandbox (`run_tests`),
git subprocesses allowed. All offline; no new dependency.

## Technical Context

**Language/Version**: Python 3.11+ (existing codebase; the tz-aware form is standard-lib).

**Primary Dependencies**: none new. `datetime.timezone` is stdlib. The invariant tests
use `ast` (stdlib) + the existing `SourceType` rank map (`sr_agent/models/memory.py`).

**Storage**: N/A — timestamps still stored as the same values (isoformat strings /
datetime objects), only the UTC instant is now tz-aware.

**Testing**: pytest, offline. US1's proof is the suite running warning-free from these
sites; US2/US3 are new `tests/architecture/` tests (SourceType ordering; AST scan of
the harness's subprocess calls). No model, Docker, or network (FR-006).

**Target Platform**: local dev machine; CI-safe.

**Project Type**: single project — 5 mechanical edits in `sr_agent/…` + two test files
in `tests/architecture/`.

**Performance Goals**: N/A (mechanical + tests).

**Constraints**: no behavior change / no timestamp-meaning change (FR-002/FR-007); no
new dependency (FR-007); the harness-exec invariant must ALLOW the existing git
subprocesses (FR-005). tz-aware isoformat adds a `+00:00` offset — safe because no code
parses these strings back (verified, spec Edge Cases).

**Scale/Scope**: 6 call-site replacements (+`timezone` import per file), one SourceType
invariant test, one harness-sandbox invariant test.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Secure-Kernel Trust Invariants** — PASS, and STRENGTHENED. US2 adds the first
  test pinning the SourceType trust-hierarchy ordering Principle I depends on; US3 adds
  the first test guarding the sandboxed-execution requirement against a harness bypass.
  The datetime change is mechanical, same instant — no trust/`SourceType`/memory/budget
  semantics touched.
- **II. Human Authority for Privileged & Irreversible Actions** — PASS. No new
  privileged/irreversible action; timestamps are metadata, the invariants are tests.
- **III. Kernel / Capability-Pack Separation** — PASS. No pack boundary touched; the
  harness-exec invariant reads the harness source, doesn't change the boundary.
- **IV. Human-Gated Knowledge Promotion** — PASS. No knowledge writes.
- **V. No Paid-API Dependency** — PASS. No API; tests offline (FR-006).

This feature is squarely the constitution's "Development Workflow & Quality Gates"
(test-first for security-critical behavior — here, pinning two invariants). No
violations — Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/013-cleanup-invariants/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (the two invariants)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
sr_agent/
├── cli.py                          # datetime.utcnow() → datetime.now(timezone.utc)
├── packs/audit/checkpoint.py       #   (+ add `timezone` to the datetime import
├── packs/audit/report.py           #    at each of the 6 sites)
├── orchestrator/relay.py
└── orchestrator/confirmation.py    # (2 sites: created_at, decided_at)

tests/architecture/
├── test_source_type_hierarchy.py   # NEW: pins the SourceType trust ranking (US2)
└── test_harness_sandbox_only.py    # NEW: AST-asserts the harness executes PoC/forge
                                     #   only via run_tests; git subprocesses allowed (US3)
```

**Structure Decision**: Single project. The datetime fix is 6 mechanical edits across 5
kernel/pack files (add `timezone` to each `from datetime import …`, swap the call). The
two invariants are new files under the existing `tests/architecture/` tier — the
SourceType one imports the real rank map and asserts the ordering; the harness one
`ast`-parses `scripts/poc_queue_runner.py` and asserts every `subprocess` call is a git
command (PoC/forge execution goes only through `run_tests`).

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*

**Post-design re-check (after Phase 0/1)**: research.md's decisions (tz-aware
replacement; import the rank map for US2; AST-scan subprocess commands for US3)
introduce no new violations — still PASS, and US2/US3 strengthen Principle I.
