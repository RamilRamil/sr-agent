# Tasks: Harness Verdict-Logic Test Coverage + Orchestration Integration Test

**Input**: Design documents from `/specs/009-harness-verdict-tests/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R4), data-model.md,
contracts/process-finding.md, quickstart.md

**Tests**: This feature IS tests — every task produces or enables a test. The one
production change (US2's behavior-preserving `_process_finding` extraction, US3's
`SymbolIndex` re-platform) exists only to make behavior testable / correct.

**Organization**: By user story, priority order — US1 (P1, direct verdict/repair
tests) → US2 (P1, loop integration test, needs the extraction) → US3 (P2, scaffold
inheritance). US1 needs no production change and can land first as the MVP safety net.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files / independent, no dependency on an incomplete task
- **[Story]**: US1…US3 (Setup/Polish carry no story label)

---

## Phase 1: Setup

- [X] T001 Confirm `tests/integration/` exists (it does, already tracked with ~20
  tests) and is discovered under the offline pytest invocation — the US2 loop test
  lands there. NOTE: this session's ad-hoc "full suite" command
  (`tests/unit tests/architecture tests/security tests/frontend`) had been silently
  OMITTING `tests/integration` — corrected to include it (research.md R4).

**Checkpoint**: `pytest tests/integration` collects (zero tests yet) with no error.

---

## Phase 2: Foundational

*No blocking cross-story prerequisite: US1 is pure new tests against existing
functions; US2's only prerequisite (the extraction) is inside US2; US3 is
self-contained. No shared foundational phase needed.*

---

## Phase 3: User Story 1 — The pass/fail gates can't silently regress (Priority: P1) 🎯 MVP

**Goal**: Every verdict gate + deterministic repair helper has a direct offline test
pinning the exact bug classes seen this session.

**Independent Test**: quickstart.md #1/#2 — run `tests/unit/test_poc_queue_runner.py`;
each gate/helper has a test; re-breaking `_compiled` to a denylist fails a test.

### Tests for User Story 1

- [X] T002 [P] [US1] In `tests/unit/test_poc_queue_runner.py`, add
  `test_compiled_positive_signal_only` — `_compiled` returns True only for output that
  actually ran a suite (`Ran N tests`), and False for a compile failure worded
  differently from any known phrase (the spec-006 regression, FR-002/SC-001).
- [X] T003 [P] [US1] Add `test_poc_defects_flags_empty_mock_and_missing_import` —
  `_poc_defects` flags an empty/fully-commented test, a re-declared/mocked target
  contract, and a missing target import (FR-003).
- [X] T004 [P] [US1] Add `test_stall_signature_keys_on_message_not_line` — two attempts
  whose identical error lands on different line numbers produce the SAME stall
  signature (FR-004). (Test the signature-derivation helper directly; if it's currently
  inline in the loop, factor the minimal signature computation into a named helper as
  part of this task so it's unit-addressable.)
- [X] T005 [P] [US1] Add `test_repair_helpers_transform` — one focused assertion each
  for `_targeted_hints`/`_line_level_hints`/`_sig_by_method` (resolve a forge error to
  the real signature/path hint), `_fix_setup_override` (strip non-virtual setUp,
  re-inject statements), `_fix_import_paths` (bare-SPDX + wrong-depth fix), and
  `revert_hints` (compiled-but-reverted feedback block) (FR-005). Synthetic input only,
  no target-project code (FR-009).

### Implementation for User Story 1

- [X] T006 [US1] If T004 required naming the stall-signature computation, make that the
  only production change here — a behavior-preserving extraction of the existing inline
  `error_sig`/`fail_sig` derivation into a helper `main()` still calls identically.
  Otherwise this task is a no-op confirmation.

**Checkpoint**: 100% of verdict gates + repair helpers have a direct test (SC-002); the
spec-006 denylist bug can't return silently (SC-001). MVP safety net in place.

---

## Phase 4: User Story 2 — The whole draft→fix loop is testable without a live model (Priority: P1)

**Goal**: The per-finding orchestration is exercisable end-to-end offline through a
fake model + fake sandbox, covering the five outcome paths.

**Independent Test**: quickstart.md #3 — `tests/integration/test_poc_runner_loop.py`
passes five scenarios with no Ollama/Docker/network.

### Implementation for User Story 2

- [X] T007 [US2] Extract `main()`'s per-finding loop body into `_process_finding(...)`
  in `scripts/poc_queue_runner.py` per contracts/process-finding.md — behavior-
  preserving: same events/order, same outcome strings, same file writes, no `sys.exit`
  in the body. `main()` calls it inside `for task in todo:` with the budget/wall-clock
  guard staying in `main()` (research.md R1).
- [X] T008 [US2] Run the full existing suite to confirm the extraction changed no
  behavior (the live-run event shapes this session already logged are the reference);
  fix any drift before writing new tests against it.

### Tests for User Story 2

- [X] T009 [P] [US2] In `tests/integration/test_poc_runner_loop.py`, add the fake-model
  (scripted `pqr.draft`/`pqr.fix`) and fake-sandbox (scripted `pqr.run_tests` returning
  `TestResult`) doubles per data-model.md, plus a capturing `log`.
- [X] T010 [P] [US2] `test_loop_clean_pass` — first draft passes with no defects →
  outcome `passed`, expected events emitted (depends on T007, T009).
- [X] T011 [P] [US2] `test_loop_vacuous_pass_rejected` — `run_tests` passes but code is
  empty/mock/no-import → outcome `vacuous_pass`, `rejected_vacuous` event (T007, T009).
- [X] T012 [P] [US2] `test_loop_compile_error_then_repair` — draft has a compile error,
  the scripted fix corrects it → a repair round runs and the corrected outcome is
  reached (T007, T009).
- [X] T013 [P] [US2] `test_loop_stall_exhausts` — every attempt returns the identical
  failure → stall detected, outcome `exhausted` (T007, T009).
- [X] T014 [P] [US2] `test_loop_budget_stop` — more findings/attempts than budget
  allows → loop stops at the budget without starting the next finding (this asserts the
  `main()`-level guard, so drive it at whatever level exposes the budget cleanly)
  (T007, T009).

**Checkpoint**: the five outcome paths are covered offline (SC-003); a control-flow or
outcome-classification regression is caught locally in seconds, not in a live run.

---

## Phase 5: User Story 3 — The scaffold-sufficiency check understands inheritance (Priority: P2)

**Goal**: `scaffold_missing_types` resolves state variables provided via an inherited
parent base, via the AST-backed `SymbolIndex`.

**Independent Test**: quickstart.md #4 — an inherited-var scaffold is not flagged; a
genuinely-missing one is.

### Tests for User Story 3

- [X] T015 [P] [US3] In `tests/unit/test_poc_queue_runner.py`, add
  `test_scaffold_missing_types_sees_inherited_var` — a scaffold whose needed type's
  state variable is declared in a parent base it inherits is NOT reported missing
  (FR-008/SC-004); and `test_scaffold_missing_types_still_flags_truly_absent` — a
  scaffold declaring nothing of that type anywhere in its chain IS reported missing.
  Update the existing 2026-07-06 tests if their expectations change under AST
  resolution.

### Implementation for User Story 3

- [X] T016 [US3] Re-platform `scaffold_missing_types` in `scripts/poc_queue_runner.py`
  onto `SymbolIndex` (research.md R3): resolve the scaffold contract's inheritance
  chain and treat a target type as provided if any contract in its body or transitive
  parents declares a `state_var` of that type. Keep it diagnostic-only (non-gating) and
  its `scaffold_insufficient` log event unchanged (depends on T015 failing first).

**Checkpoint**: the regex inheritance-blindness is gone; the check no longer
false-flags a scaffold whose deployment variable is inherited (SC-004).

---

## Phase 6: Polish & Cross-Cutting

- [X] T017 Run the full offline suite
  (`tests/unit tests/integration tests/architecture tests/security tests/frontend`) and
  confirm all green with the new tests, entirely offline, no target-project code
  embedded (SC-005/FR-009).
- [X] T018 Update `docs/roadmap.md` recording that step 1 of the harness-review
  remediation landed (verdict/loop test coverage + scaffold inheritance fix), and
  noting the remaining review findings deferred to their own specs (mutation-based PASS
  verification; Stage 1 large-model scaffold synthesis; datetime deprecation cleanup;
  additional architecture invariants).

---

## Dependencies & Execution Order

- **Setup (T001)** → **US1 (T002-T006)**, the MVP, needs nothing else and lands first.
- **US2 (T007-T014)**: T007 (extraction) before T009-T014; T008 guards the extraction.
- **US3 (T015-T016)**: T015 (failing tests) before T016 (re-platform).
- **Polish (T017-T018)** after all stories.
- US1, US2, US3 are largely independent (different functions/files); US2's extraction is
  the only production change the others don't depend on.

### Parallel opportunities

- US1: T002/T003/T004/T005 all parallel (independent test functions, one file — write
  as one batch).
- US2: T010-T014 parallel once T007+T009 exist (independent scenarios).
- US3: T015 before T016.
- US1 can proceed fully in parallel with US3 (no shared code); US2's extraction (T007)
  is independent of both.

---

## Implementation Strategy

### MVP (Setup + US1)
Direct tests for every verdict gate + repair helper — the safety net that makes the
spec-006 class of bug impossible to reach a live run undetected. Ship and validate
before touching production code.

### Then the loop test (US2)
The one behavior-preserving extraction, guarded by the full existing suite, then five
offline scenarios covering the loop's outcome classification — moving loop-bug
detection off metered GPU runs.

### Then harden the scaffold check (US3)
Kill the last regex inheritance-blindness by reusing `SymbolIndex`.

### Notes
- No new dependency; all offline (FR-009).
- No kernel change; confined to the standalone harness + its tests.
- Every test uses synthetic Solidity or existing offline fixtures — never a bug-bounty
  target's code/names/paths.
- Commit per task or logical group (on explicit request per project convention).
