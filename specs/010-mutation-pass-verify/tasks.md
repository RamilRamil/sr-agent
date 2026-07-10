# Tasks: Mutation-Based PASS Verification

**Input**: Design documents from `/specs/010-mutation-pass-verify/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R4), data-model.md,
contracts/mutation-verify.md, quickstart.md

**Tests**: INCLUDED — this feature's completion bar (SC-001–005) is explicitly offline,
and it strengthens a verdict, so it must itself be tested. Every scenario maps to a
task below. Live H-01 (US3) is optional.

**Organization**: By user story, priority order — US1 (P1, MVP: the verified/
unverified gate) → US2 (P2, honest `unavailable` fallback) → US3 (P3, optional live).
US1 and US2 share the Foundational fix-extraction + diff-apply building blocks.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files / independent, no dependency on an incomplete task
- **[Story]**: US1…US3 (Setup/Foundational/Polish carry no story label)

---

## Phase 1: Setup

- [X] T001 Confirm the feasibility premise offline: the session's report
  (`audit/contracts-pashov-…md`, external path) parses into ordered finding-sections
  with fenced ` ```diff ``` ` blocks, and at least one finding (e.g. #4) has none — a
  sanity checkpoint for the R1 extractor, no code. (Skip if the external report path is
  absent.)

**Checkpoint**: the report layout the extractor targets is confirmed present.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ blocks US1 and US2** — both need a fix to apply and a verify function to call.

- [X] T002 [P] Implement `extract_fix_for_finding(report_text, task) -> str | None` in
  `scripts/poc_queue_runner.py` (contracts/mutation-verify.md, R1): parse the report
  into ordered finding-sections, associate `task` by extraction order + a title-overlap
  sanity check, return the fenced diff VERBATIM or `None`. Deterministic — never via the
  model.
- [X] T003 [P] Implement `_git_apply(copy_dir, diff) -> bool` in
  `scripts/poc_queue_runner.py` (R2): apply via `git apply`, fall back to
  `patch -p1 --forward`; return whether it applied cleanly. No fuzzy patching (FR-009).
- [X] T004 Implement `mutation_verify(project, task, poc_rel_path, sandbox, log, *,
  run_tests=run_tests, fork_rpc=None, image=None) -> str` in
  `scripts/poc_queue_runner.py` (contracts/mutation-verify.md): ephemeral copytree
  (exclude `out/`/`cache_forge/`, FR-004) → `_git_apply` → re-run the SAME PoC via
  `run_tests` → classify per the verdict table; delete the copy in `finally` (depends
  on T002, T003).

**Checkpoint**: fix extraction, diff apply, and the verify classifier exist and are
independently callable; nothing wired into the loop yet.

---

## Phase 3: User Story 1 — A PASS that survives the fix is caught (Priority: P1) 🎯 MVP

**Goal**: a genuine PASS is re-run against the applied fix; a survivor becomes
`unverified_pass`, a PoC that now fails is a verified pass.

**Independent Test**: quickstart.md #3 — scripted patched-run fails → verified; still
passes → `unverified_pass`.

### Tests for User Story 1

- [X] T005 [P] [US1] `tests/unit/test_poc_queue_runner.py::test_extract_fix_verbatim` —
  `extract_fix_for_finding` pulls a synthetic report's fenced diff byte-for-byte and
  returns `None` for a finding with no `**Fix**` block (FR-001, quickstart #1).
- [X] T006 [P] [US1] `tests/unit/test_poc_queue_runner.py::test_git_apply_real_diff` —
  a real small unified diff applies to a real tmp source via `_git_apply`, and the
  source fixture is byte-for-byte unchanged afterward is NOT asserted here (that's the
  copy); assert the diff applied and the patched file reflects it (FR-004 asserted at
  the mutation_verify level in T008).
- [X] T007 [P] [US1] `tests/unit/test_poc_queue_runner.py::test_mutation_verify_verdicts`
  — with a real tmp project + real diff and a scripted `run_tests`: patched-run FAILS →
  `"verified"` + `mutation_verified`; patched-run PASSES → `"unverified_pass"` +
  `mutation_unverified`; assert the real project tree is unchanged after (SC-004/FR-004).

### Implementation for User Story 1

- [X] T008 [US1] Wire `mutation_verify` into `_process_finding`'s `real_pass` branch in
  `scripts/poc_queue_runner.py` (contracts/mutation-verify.md): `unverified_pass` verdict
  downgrades `outcome`; `verified`/`unavailable` keep `passed`. No other outcome path
  calls it (FR-007) (depends on T004).
- [X] T009 [US1] Extend `tests/integration/test_poc_runner_loop.py` with
  `test_loop_mutation_verified` and `test_loop_mutation_unverified_pass` — via the spec-009
  fake sandbox, the vulnerable run PASSES (loop's normal path) and the patched re-run is
  one more scripted `run_tests` result: fail → outcome `passed` + `mutation_verified`;
  pass → outcome `unverified_pass` + `mutation_unverified` (SC-001/SC-002; depends on T008).

**Checkpoint**: the 2026-07-06 false-positive class (a defect-free PASS unrelated to the
exploit) is now caught as `unverified_pass` offline — the MVP gate.

---

## Phase 4: User Story 2 — Never fabricate a failure it can't substantiate (Priority: P2)

**Goal**: no fix / non-applying diff / non-building patch / infra error all keep
`passed` and log `mutation_verify_unavailable` with a reason.

**Independent Test**: quickstart.md #3's third bullet — unavailable paths never
downgrade.

### Tests for User Story 2

- [X] T010 [P] [US2] `tests/unit/test_poc_queue_runner.py::test_mutation_verify_unavailable`
  — `fix=None` → `unavailable(no_fix)`; a diff that won't apply → `unavailable(patch_failed)`;
  a scripted patched-run that doesn't compile (`_compiled` False) → `unavailable(patched_no_build)`;
  a scripted sandbox error → `unavailable(infra)` — each keeps the pass (FR-005/FR-006).
- [X] T011 [P] [US2] `tests/integration/test_poc_runner_loop.py::test_loop_mutation_unavailable`
  — a passing PoC whose finding has no applicable fix keeps outcome `passed` and logs
  `mutation_verify_unavailable` (SC-003; depends on T008).

### Implementation for User Story 2

- [X] T012 [US2] Confirm the T004 classifier already yields every `unavailable` reason
  correctly (no_fix / patch_failed / patched_no_build / infra); fix any gap T010/T011
  reveal so a downgrade NEVER rests on anything but a real test FAILURE on a built
  patched source.

**Checkpoint**: the verifier degrades honestly — 0 false downgrades (SC-003).

---

## Phase 5: User Story 3 — Optional live confirmation (Priority: P3)

- [ ] T013 [US3] (OPTIONAL, not required for completion) If a live H-01 run reaches a
  PASS, let mutation-verify run against the finding's real fix and record the verdict.
  Depends on US1/US2 complete.
- [ ] T014 [US3] (OPTIONAL, only if T013 is run) Record honestly in `docs/roadmap.md`
  whether the live pass verified, downgraded to `unverified_pass`, or was unavailable —
  a downgrade is an informative, acceptable outcome.

---

## Phase 6: Polish & Cross-Cutting

- [X] T015 Run the full offline suite
  (`tests/unit tests/integration tests/architecture tests/security tests/frontend`) and
  confirm all green with the new tests, offline, no target-project code embedded
  (SC-005/FR-008).
- [X] T016 Update `docs/roadmap.md`: step 2 of the harness-review remediation landed
  (mutation-based PASS verification), and note the remaining deferred findings (Stage 1
  scaffold synthesis; datetime deprecation cleanup; extra architecture invariants).

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002-T004)** → user stories.
- **US1 (T005-T009)** is the MVP: verified/unverified gate end-to-end. T005/T006/T007
  after T002-T004; T008 before T009.
- **US2 (T010-T012)** depends on T004 (classifier) + T008 (wiring); mostly proves the
  unavailable paths never downgrade.
- **US3 (T013-T014)** optional, after US1/US2.
- **Polish (T015-T016)** last.

### Parallel opportunities

- Foundational: T002/T003 parallel (independent functions); T004 after both.
- US1: T005/T006/T007 parallel (independent tests); T008 before T009.
- US2: T010/T011 parallel.
- US1's tests and US2's tests are independent once T004/T008 exist.

---

## Implementation Strategy

### MVP (Setup + Foundational + US1)
The verified/unverified gate working end-to-end offline — the exact class of false
positive from 2026-07-06 is now caught. STOP and validate offline before any live run.

### Then harden honesty (US2)
Prove every unavailable path keeps `passed` — a verifier that false-downgrades would be
worse than none.

### Then, optionally, live (US3)
Only if a live H-01 reaches a PASS worth verifying; a downgrade is a valid result.

### Notes
- No new dependency; `git apply`/`patch` are standard tooling; all offline (FR-008).
- No kernel change; confined to the standalone harness + its tests.
- Every test uses synthetic Solidity + a synthetic diff — never a bug-bounty target's
  code/names/paths.
- Commit per task or logical group (on explicit request per project convention).
