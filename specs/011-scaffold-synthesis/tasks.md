# Tasks: Stage 1 Scaffold Synthesis

**Input**: Design documents from `/specs/011-scaffold-synthesis/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R4), data-model.md,
contracts/synthesize-scaffold.md, quickstart.md

**Tests**: INCLUDED — the completion bar (SC-001–005) is explicitly offline, and this
generates + runs code, so it must be tested. Every scenario maps to a task. Live H-01
(US3) is optional.

**Organization**: By user story, priority order — US1 (P1, MVP: synthesize + use) →
US2 (P1, compile-validate + honest fallback) → US3 (P3, optional live). US1 and US2
share the Foundational `synthesize_scaffold` function; US2 is mostly its failure paths.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files / independent, no dependency on an incomplete task
- **[Story]**: US1…US3 (Setup/Foundational/Polish carry no story label)

---

## Phase 1: Setup

- [X] T001 Add a `SYNTH_SCAFFOLD_PROMPT` constant to `scripts/poc_queue_runner.py`
  (research.md R2): given the missing contract type(s)' real source + the existing
  auto-discovered scaffold as a pattern, instruct the model to produce a Foundry
  abstract base that inherits the existing base, declares the missing contract as a
  state variable, and deploys/wires it in a setup helper — return ONLY Solidity.

**Checkpoint**: the synthesis prompt exists and renders with its placeholders.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ blocks US1 and US2** — both need the synthesis+validation function.

- [X] T002 Implement `synthesize_scaffold(project, task, missing_types,
  existing_scaffold, symbol_index, client, sandbox, log, *, image=None, fork_rpc=None)
  -> Path | None` in `scripts/poc_queue_runner.py` (contracts/synthesize-scaffold.md):
  ground on the missing type(s)' source (`read_location_source`/`SymbolIndex`),
  `client.generate` the base, `_strip_fences`, reject non-Solidity output
  (`no_output`), write to `audit/poc/_synth/<Name>.sol` (untracked), write + run a
  minimal inheriting smoke test via `run_tests`, gate on `_compiled` (`no_build`
  discards + removes the base), handle an infra error (`infra`), remove the smoke test
  in `finally`, and return the base path on success (depends on T001).
- [X] T003 Add a `--no-scaffold-synthesis` CLI flag (default: synthesis ON) to
  `main()` and thread its value into `_process_finding` (research.md R1).

**Checkpoint**: `synthesize_scaffold` exists and is independently callable; the flag
exists. Nothing wired into the loop's scaffold selection yet.

---

## Phase 3: User Story 1 — A missing deploy-base is synthesized and used (Priority: P1) 🎯 MVP

**Goal**: an insufficient-scaffold finding gets a synthesized, compiling base and drafts
under it.

**Independent Test**: quickstart.md #1/#3 — synthesis returns a base that compiles →
the finding's scaffold is swapped to it.

### Tests for User Story 1

- [X] T004 [P] [US1] `tests/unit/test_poc_queue_runner.py::test_synthesize_scaffold_accepts_compiling`
  — a fake `client.generate` returns a Solidity base + a scripted `run_tests` COMPILES:
  `synthesize_scaffold` returns the base's `Path`, the file lives under `audit/poc/_synth/`,
  and `scaffold_synthesized` is logged (FR-003/FR-004; SC-001).
- [X] T005 [P] [US1] `tests/unit/test_poc_queue_runner.py::test_synthesize_writes_only_audit_area`
  — after synthesis (accept or reject) the project's tracked source is byte-for-byte
  unchanged; the smoke test file is gone; a rejected base is removed (FR-006/SC-004).

### Implementation for User Story 1

- [X] T006 [US1] Wire `synthesize_scaffold` into `_process_finding`'s insufficiency
  branch in `scripts/poc_queue_runner.py` (contracts/synthesize-scaffold.md): on a
  returned path, swap `scaffold_paths`/`scaffold`/`guard` to the synthesized base before
  the draft loop; on `None`, keep the prior scaffold. Gate on `--no-scaffold-synthesis`
  (depends on T002, T003).
- [X] T007 [US1] `tests/integration/test_poc_runner_loop.py::test_loop_synth_used_on_success`
  — an insufficient-scaffold finding with a monkeypatched `synthesize_scaffold` returning
  a base path drafts under the synthesized base (assert the swap happened, e.g. via the
  grounding/scaffold in the emitted events or the scaffold text reaching draft)
  (depends on T006).

**Checkpoint**: an insufficient finding is no longer dead on arrival — it drafts under a
synthesized, compiling base (the H-01 blocker, closed offline). MVP.

---

## Phase 4: User Story 2 — Trusted only if it compiles; honest fallback (Priority: P1)

**Goal**: a non-compiling / no-output / infra-failed synthesis is discarded and the
run falls back honestly, never blocked, never using a bad base.

**Independent Test**: quickstart.md #2 — each failure path returns None + the right
reason and keeps the prior scaffold.

### Tests for User Story 2

- [X] T008 [P] [US2] `tests/unit/test_poc_queue_runner.py::test_synthesize_scaffold_failure_paths`
  — scripted `run_tests` NOT compiled → `None` + `scaffold_synthesis_failed(no_build)`
  and the base file removed; fake client returns non-Solidity/empty → `None`
  + `no_output`; `run_tests` raises → `None` + `infra` (FR-004/FR-005/SC-002).
- [X] T009 [P] [US2] `tests/integration/test_poc_runner_loop.py::test_loop_synth_fallback_on_failure`
  — a monkeypatched `synthesize_scaffold` returning `None` leaves the finding on its
  prior scaffold and the run proceeds (not blocked); and
  `test_loop_synth_skipped_when_sufficient` — a finding whose scaffold is SUFFICIENT
  never consults synthesis (SC-002/SC-003; depends on T006).

### Implementation for User Story 2

- [X] T010 [US2] Confirm the T002 classifier already emits every failure reason
  (`no_output`/`no_build`/`infra`) and removes artifacts; fix any gap T008/T009 reveal
  so a bad base is NEVER used and tracked source is NEVER touched.

**Checkpoint**: the verifier of the verifier — a synthesized base is used only on a real
compile; every other path is an honest, logged fallback (SC-002).

---

## Phase 5: User Story 3 — Optional live H-01 end-to-end (Priority: P3)

- [ ] T011 [US3] (OPTIONAL, not required for completion) A live H-01 run where the
  auto-scaffold is insufficient, through synthesis → drafting → (spec 010)
  mutation-verify. Depends on US1/US2 complete.
- [ ] T012 [US3] (OPTIONAL, only if T011 is run) Record honestly in `docs/roadmap.md`:
  did the synthesized `SharesCooldown` base compile? did H-01 reach a PASS? was it
  mutation-verified or downgraded? Non-convergence is acceptable.

---

## Phase 6: Polish & Cross-Cutting

- [X] T013 Run the full offline suite
  (`tests/unit tests/integration tests/architecture tests/security tests/frontend`) and
  confirm all green with the synthesis scenarios, offline, no target code embedded
  (SC-005/FR-007).
- [X] T014 Update `docs/roadmap.md`: step 3 of the harness-review remediation landed
  (scaffold synthesis closes the detect→hand-write loop), and note the remaining
  deferred findings (harness prompt management; datetime deprecation + architecture
  invariants).

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002-T003)** → user stories.
- **US1 (T004-T007)**: the synthesize+use MVP. T004/T005 after T002; T006 before T007.
- **US2 (T008-T010)**: depends on T002 (function) + T006 (wiring); mostly the failure
  paths.
- **US3 (T011-T012)** optional, after US1/US2.
- **Polish (T013-T014)** last.

### Parallel opportunities

- Foundational: T002 then T003 (T003 is a small flag, independent — can be [P] with T002
  but T002 is the bulk).
- US1: T004/T005 parallel; T006 before T007.
- US2: T008/T009 parallel.
- US1 tests and US2 tests independent once T002/T006 exist.

---

## Implementation Strategy

### MVP (Setup + Foundational + US1)
An insufficient finding drafts under a synthesized, compiling base — the H-01 structural
blocker closed, offline. STOP and validate before any live run.

### Then harden honesty (US2)
Prove a bad base is never used and the fallback is honest — a poisoned scaffold would
fail every draft, strictly worse than none.

### Then, optionally, live (US3)
The ultimate end-to-end: does a synthesized SharesCooldown base finally let H-01 reach a
mutation-verified PASS? A non-convergence is a valid result.

### Notes
- No new dependency; uses the harness's existing model + sandbox; all offline (FR-007).
- No kernel change; confined to the standalone harness + its tests.
- Every test uses synthetic Solidity — never a bug-bounty target's code/names/paths.
- Any PASS under a synthesized base is still mutation-verified (spec 010, FR-008).
- Commit per task or logical group (on explicit request per project convention).
