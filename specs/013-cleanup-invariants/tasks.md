# Tasks: Deprecation Cleanup + Architecture-Invariant Guards

**Input**: Design documents from `/specs/013-cleanup-invariants/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R4), data-model.md,
contracts/invariants.md, quickstart.md

**Tests**: INCLUDED — US2/US3 ARE tests (the invariants); US1's proof is the suite
running warning-free. Every SC maps to a task. All offline.

**Organization**: By user story — US1 (P1, deprecation fix) → US2 (P1, SourceType
invariant) → US3 (P2, harness-sandbox invariant). Independent; no shared foundation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files / independent
- **[Story]**: US1…US3 (Polish carries no story label)

---

## Phase 1: Setup

- [X] T001 Confirm the 6 `datetime.utcnow()` sites and that none of their outputs are
  parsed back / shape-pinned by a test (research.md R1) — a pre-edit sanity check, no
  code. (Already verified in spec Edge Cases; re-confirm before editing.)
  **CORRECTION**: a bare-`utcnow` scan found **5 additional** `default_factory=datetime.utcnow`
  sites (memory.py, chat.py ×2, session.py ×2) — same deprecation, extended into US1.

**Checkpoint**: the tz-aware replacement is confirmed safe at all 6 sites.

---

## Phase 2: User Story 1 — No deprecated timestamp calls (Priority: P1) 🎯 MVP

**Goal**: zero `datetime.utcnow()`; same UTC instant; no regression.

**Independent Test**: quickstart.md #1.

### Implementation for User Story 1

- [X] T002 [P] [US1] Replace `datetime.utcnow()` → `datetime.now(timezone.utc)` in
  `sr_agent/cli.py:97` and add `timezone` to its `from datetime import datetime` (FR-001).
- [X] T003 [P] [US1] Same in `sr_agent/packs/audit/checkpoint.py:26` (+ import).
- [X] T004 [P] [US1] Same in `sr_agent/packs/audit/report.py:64` (+ import).
- [X] T005 [P] [US1] Same in `sr_agent/orchestrator/relay.py:84` (isoformat string; + import).
- [X] T006 [P] [US1] Same in `sr_agent/orchestrator/confirmation.py:53` and `:131`
  (created_at + decided_at, isoformat strings; + import).
- [X] T006a [P] [US1] (scope correction) Replace the 5 `default_factory=datetime.utcnow`
  references with `default_factory=lambda: datetime.now(timezone.utc)` (+ `timezone`
  import) in `sr_agent/models/memory.py:60`, `sr_agent/models/chat.py:96,128`,
  `sr_agent/packs/audit/session.py:46,59`.

### Tests for User Story 1

- [X] T007 [US1] Verify: `grep -rn "utcnow" sr_agent` yields nothing (CLEAN), and the
  previously-warning tests pass with the `utcnow` deprecation escalated to error
  (272 passed, 0 utcnow warnings) (FR-003/SC-001/SC-002; depends on T002-T006a).

**Checkpoint**: the deprecation is gone; timestamps mean the same instant; suite green.

---

## Phase 3: User Story 2 — SourceType trust hierarchy pinned (Priority: P1)

**Goal**: the trust ranking Principle I depends on fails a test if reordered.

**Independent Test**: quickstart.md #2.

- [X] T008 [US2] Add `tests/architecture/test_source_type_hierarchy.py`
  (contracts/invariants.md): import the real rank map from `sr_agent/models/memory.py`,
  assert `human_input > tool_output > external_llm_output == human_relayed_tool >
  llm_inference`, and include an assertion demonstrating a simulated reorder violates a
  relation (FR-004/SC-003).

**Checkpoint**: a silent reranking of the trust hierarchy now fails a test.

---

## Phase 4: User Story 3 — Harness executes PoCs only via the sandbox (Priority: P2)

**Goal**: no direct forge/PoC execution can be added to the harness undetected.

**Independent Test**: quickstart.md #3.

- [X] T009 [US3] Add `tests/architecture/test_harness_sandbox_only.py`
  (contracts/invariants.md): `ast`-parse `scripts/poc_queue_runner.py`, collect every
  `subprocess.run`/`Popen` call, assert each command's first list element is in the benign
  allowlist `{"git", "patch"}` (mutation-verify's `git apply`/`git ls-files` + its `patch`
  fallback; PoC/forge goes via `run_tests`), and include a negative check on a
  synthetic `subprocess.run(["forge","test"])` AST proving the guard catches it
  (FR-005/SC-004).

**Checkpoint**: a future direct forge-exec in the harness fails a test.

---

## Phase 5: Polish & Cross-Cutting

- [X] T010 Run the full offline suite
  (`tests/unit tests/integration tests/architecture tests/security tests/frontend`) and
  confirm all green with the two new invariants, zero `utcnow` warnings, no new
  dependency (SC-005/FR-006/FR-007). **RESULT: 383 passed, 2 skipped, 3 warnings**
  (down from 178 — the residual 3 are unrelated: `asyncio_mode` config + Starlette/httpx).
- [X] T011 Update `docs/roadmap.md`: item 5 landed — the harness-review remediation arc
  (specs 006-013) is complete.

---

## Dependencies & Execution Order

- **Setup (T001)** → **US1 (T002-T007)**; T002-T006 parallel (different files), T007
  after.
- **US2 (T008)** and **US3 (T009)** are independent of US1 and each other — fully
  parallel.
- **Polish (T010-T011)** last.

### Parallel opportunities

- T002/T003/T004/T005/T006 all parallel (distinct files).
- T008 and T009 parallel with each other and with US1.

---

## Implementation Strategy

### MVP (Setup + US1)
Remove the deprecation — forward-compat, warning-free suite, same instants. Ship first.

### Then pin the invariants (US2, US3)
Two focused offline tests that turn two currently-implicit security properties into
enforced ones — a reorder or a sandbox bypass now fails CI.

### Notes
- Mechanical + tests only; no feature behavior change, no new dependency (FR-007).
- US2/US3 strengthen Principle I; the datetime change touches only the deprecated call.
- Commit per task or logical group (on explicit request per project convention).
