# Tasks: Make Falsification-Verification Actually Run

**Feature**: `025-mutation-verify-repair` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: one new module (`scripts/patch_reconstruct.py`), ~45 changed lines in
`scripts/poc_queue_runner.py`, one new unit test file, one new architecture test, and extensions to two
existing test files. No new dependencies, no kernel/pack changes.

**Tests ARE requested** — FR-016 makes offline deterministic tests part of the feature, so each story
writes its tests before its implementation.

**Test placement follows the layout the repo documents in-file**: `test_poc_runner_loop.py` states that
loop-level verdict/outcome behavior is tested there, while `mutation_verify`'s internals are unit-tested
in `test_poc_queue_runner.py`. US1/US2 are loop behavior → they extend the integration file and reuse its
`_run_with_mutverify` harness. Only reconstruction is a genuinely new unit.

**Non-negotiable test rule (US3/US4)**: every reconstruction success case MUST assert the REAL
`git apply` accepts the output against a temp git repo. A string-comparison test would have passed on
the illustrative diff too and caught nothing — the whole bug is that something *looked* like a patch
and no tool would take it (research Decision 7).

**Fixture rule (non-negotiable, every test task)**: fixtures are **invented**, reproducing only the
SHAPE of an illustrative diff. No name, path, or contract identifier from any audited target enters
this repo (memory `feedback_no_target_code_in_agent`; enforced by
`tests/architecture/test_no_target_material.py`). The live report grounds the design; it stays outside.

---

## Phase 1: Setup

- [X] T001 Create `tests/unit/test_patch_reconstruct.py` with a docstring naming feature 025 US3/US4 and the offline/synthetic-fixture contract, a `_git_repo(tmp_path, files)` helper that inits a real temp git repo (`git init`, write, add, commit), and an `_applies(repo, patch) -> bool` helper running the REAL `git apply`

---

## Phase 2: Foundational (blocking prerequisites for all stories)

**Purpose**: make the reason for a non-verification reach the caller. Today `mutation_verify` logs all
five reasons internally and returns a bare `"unavailable"`, so the outcome cannot tell them apart.

- [X] T002 Change `mutation_verify` in `scripts/poc_queue_runner.py` (~line 1676) to return `(status, reason)` — status `verified` / `unverified_pass` / `unavailable`; reason `no_fix` / `reconstruction_refused` / `patch_failed` / `patched_no_build` / `infra` / `""` — preserving today's control flow and every existing log event exactly (FR-003, FR-014). Note in a comment that `reconstruction_refused` is emitted only once US4 wires reconstruction in (T038); it is declared here so the vocabulary lands in one place
- [X] T003 Update the single call site in `_process_finding` (~line 2287) in `scripts/poc_queue_runner.py` to unpack the tuple; behavior unchanged at this task (the outcome split lands in US1)
- [X] T004 Update the 8 existing assertions in `tests/unit/test_poc_queue_runner.py` (~lines 630–681) from `mutation_verify(...) == "<string>"` to the tuple contract, keeping each test's original intent and additionally pinning the reason now returned
- [X] T005 Update the two `mutation_verify` monkeypatch fakes in `tests/integration/test_poc_runner_loop.py` (~lines 174, 243) to return the tuple contract

**Checkpoint**: the reason reaches the caller; no user-visible behavior has changed; full suite green.

---

## Phase 3: User Story 1 — verified vs unchecked are distinguishable (Priority: P1)

**Goal**: an operator can tell from the outcome alone whether falsification ran, and if not, why.

**Independent test**: a pass whose verification ran and one whose verification could not run report
different outcomes, the latter carrying its reason.

### Tests for User Story 1

- [X] T006 [P] [US1] Test in `tests/integration/test_poc_runner_loop.py` via `_run_with_mutverify`: verdict `verified` → outcome `passed_verified` (US1 scenario 1)
- [X] T007 [P] [US1] Test in `tests/integration/test_poc_runner_loop.py`: verdict `unavailable` with each of the five reasons → outcome `passed_unchecked`, and the reason appears in the emitted `task_done` event (US1 scenario 2, FR-002)
- [X] T008 [P] [US1] Test in `tests/integration/test_poc_runner_loop.py`: verdict `unverified_pass` (the proof survived the fix) → outcome still `unverified_pass`, string and behavior unchanged (US1 scenario 3, FR-003)
- [X] T009 [P] [US1] Test in `tests/integration/test_poc_runner_loop.py`: no `unavailable` reason ever yields a failure outcome — assert `passed_unchecked` for all five and never `fix_failed`/`exhausted` (US1 scenario 4, FR-009, SC-006)
- [X] T010 [US1] **Trap test** in `tests/integration/test_poc_runner_loop.py`: `passed_verified`, `passed_unchecked` and `compiled` are NOT quarantined, while `unverified_pass` IS — pins the membership set that research Decision 2 found keyed on the literal `"passed"`, which would otherwise send every successful PoC to `poc_failed/`

### Implementation for User Story 1

- [X] T011 [US1] In `_process_finding` in `scripts/poc_queue_runner.py`, split the outcome (FR-001): `verified` → `passed_verified`; `unavailable` → `passed_unchecked`; `unverified_pass` unchanged. Comment WHY `passed_unchecked` is deliberately NOT named near `unverified_pass` — that name already means the OPPOSITE ("checked, and the proof survived the fix"), research Decision 1
- [X] T012 [US1] Carry the reason into the `task_done` log event in `scripts/poc_queue_runner.py` so an unchecked pass states why verification did not run (FR-002)
- [X] T013 [US1] Update the quarantine membership test in `scripts/poc_queue_runner.py` (~line 2387) from `("passed", "compiled")` to `("passed_verified", "passed_unchecked", "compiled")`, commenting that `unverified_pass` stays quarantined deliberately — a proof that survives its own fix proves nothing and belongs with the failures
- [X] T014 [US1] Rewrite the header comment at `tests/integration/test_poc_runner_loop.py` (~lines 160–163) — it currently documents the exact mapping this feature changes ("verified/unavailable keep `passed`, only unverified_pass downgrades") and would otherwise become a confident lie about the code beneath it

**Checkpoint**: US1 independently testable — T006–T010 pass; the pipeline stops misreporting.

---

## Phase 4: User Story 2 — the operator can supply the fix (Priority: P1)

**Goal**: any finding — including the 18 leads that never carry a report fix — becomes verifiable when
the operator hands over a patch.

**Independent test**: a finding with no report fix plus an operator patch → falsification runs.

### Tests for User Story 2

- [X] T015 [P] [US2] Test in `tests/integration/test_poc_runner_loop.py`: a finding with no report fix and an operator-supplied patch → falsification runs against that patch and reports on its merits (US2 scenario 1)
- [X] T016 [P] [US2] Test in `tests/unit/test_poc_queue_runner.py`: a task carrying BOTH `fix` (report) and `fix_patch` (operator) → `mutation_verify` uses the operator's patch (US2 scenario 2, FR-005, SC-005)
- [X] T017 [P] [US2] Test in `tests/unit/test_poc_queue_runner.py`: an operator patch that does not apply → `("unavailable", "patch_failed")`; never verified, never a failure (US2 scenario 3, FR-006)
- [X] T018 [P] [US2] Test in `tests/unit/test_poc_queue_runner.py`: neither `fix_patch` nor `fix` → `("unavailable", "no_fix")` — the honest floor (US2 scenario 4)
- [X] T019 [P] [US2] Test in `tests/unit/test_poc_queue_runner.py`: a `--fix-patch` path inside the agent's own project area is rejected at argument-parse time (FR-015 — patches are target material)
- [X] T020 [P] [US2] Test in `tests/unit/test_poc_queue_runner.py`: an operator patch is applied AS-IS — reconstruction is never invoked for it (FR-004); assert by monkeypatching reconstruction to raise if called

### Implementation for User Story 2

- [X] T021 [US2] Add a repeatable `--fix-patch <finding_id>=<path>` argument to `main()` in `scripts/poc_queue_runner.py`, parsing into a `{finding_id: path}` mapping, validating each path exists and resolves OUTSIDE the agent's project area using the existing external-path guard (FR-015)
- [X] T022 [US2] At the task-build site in `scripts/poc_queue_runner.py` (~line 476, where `finding["fix"]` is already attached), also attach `finding["fix_patch"]` from the operator mapping. Comment WHY two keys and not one: `fix_patch` is a REAL patch applied as-is, `fix` is an ILLUSTRATION needing reconstruction — different in kind, so the distinction is structural rather than a runtime guess (FR-004)
- [X] T023 [US2] In `mutation_verify` in `scripts/poc_queue_runner.py`, read precedence off the task — `fix_patch` → `fix` → none — and comment WHY the operator wins (a human-authored fix is the highest-trust source available; FR-005). The signature stays unchanged: resolving at build time removes the plumbing instead of threading a new parameter through

**Checkpoint**: US2 independently testable — the ceiling is gone; leads are reachable.

---

## Phase 5: User Story 3 — an illustrative fix becomes a real patch (Priority: P1)

**Goal**: the report's own fix blocks stop being dead weight.

**Independent test**: an illustrative fix whose anchors and context match a synthetic source produces
a patch that real `git apply` accepts.

### Tests for User Story 3

- [X] T024 [US3] Add synthetic fixture builders to `tests/unit/test_patch_reconstruct.py`: `_illustrative(path, hunks)` producing a block with real `---`/`+++` headers and `@@ <anchor>` markers carrying NO line numbers, plus matching `_source(...)` text — invented names only
- [X] T025 [P] [US3] Test in `tests/unit/test_patch_reconstruct.py`: exact anchor, single hunk → `reconstruct()` output is ACCEPTED by real `git apply` (US3 scenario 1)
- [X] T026 [P] [US3] Test in `tests/unit/test_patch_reconstruct.py`: removal lines carrying deep indentation → accepted by real `git apply`, indentation preserved byte-for-byte (US3 scenario 2, live trap B)
- [X] T027 [P] [US3] Test in `tests/unit/test_patch_reconstruct.py`: removals+additions with NO trailing context, near-identical except a middle line → accepted by real `git apply` (US3 scenario 3, live trap C)
- [X] T028 [P] [US3] Test in `tests/unit/test_patch_reconstruct.py`: a block with multiple hunks in one file → every hunk located independently, combined patch accepted (US3 scenario 4)
- [X] T029 [P] [US3] Test in `tests/unit/test_patch_reconstruct.py`: determinism — the same input reconstructed twice yields a byte-identical patch (SC-008)

### Implementation for User Story 3

- [X] T030 [US3] Create `scripts/patch_reconstruct.py` with a module docstring recording WHY it exists: the report's fix blocks are illustrations; both `git apply` (exit 128, "No valid patches in input") and `patch` (exit 2) reject them verbatim, so the trust mechanism ran 0 times across 10 passes in two live runs
- [X] T031 [US3] Implement `parse_illustrative(block)` in `scripts/patch_reconstruct.py`: resolve the target file from the `---`/`+++` headers and split the body into hunks at each `@@ <anchor>` marker, classifying each body line as context / removal / addition
- [X] T032 [US3] Implement `locate_anchor(source_lines, anchor)` in `scripts/patch_reconstruct.py`: return the single matching line index, requiring EXACTLY ONE verbatim match (FR-008; refusal handling lands in US4)
- [X] T033 [US3] Implement `reconstruct(block, read_source)` in `scripts/patch_reconstruct.py` (FR-007): per hunk, walk context+removal lines from the anchor requiring verbatim equality including leading whitespace (FR-008), then emit a real `@@ -a,b +c,d @@` header with correct counts; return the assembled unified diff

**Checkpoint**: US3 independently testable — T025–T029 pass with real `git apply`.

---

## Phase 6: User Story 4 — refuse rather than guess (Priority: P1)

**Goal**: the load-bearing safety property. A patch landed in the wrong place yields a WRONG
`verified` — worse than today's no-op, because the operator would believe it.

**Independent test**: abbreviated, absent and ambiguous anchors, and a mismatched context line, each
refuse with a stated reason.

### Tests for User Story 4

- [X] T034 [P] [US4] Test in `tests/unit/test_patch_reconstruct.py`: an author-abbreviated anchor (`@@ function foo(...) internal {` — an ellipsis existing nowhere verbatim) → refuses `anchor_not_found` (US4 scenario 1, live trap A — this is why 1 of the report's 3 blocks is expected to refuse BY DESIGN)
- [X] T035 [P] [US4] Test in `tests/unit/test_patch_reconstruct.py`: an anchor matching zero lines → refuses `anchor_not_found`
- [X] T036 [P] [US4] Test in `tests/unit/test_patch_reconstruct.py`: an anchor matching two lines → refuses `anchor_ambiguous`, never picks one (US4 scenario 2)
- [X] T037 [P] [US4] Test in `tests/unit/test_patch_reconstruct.py`: a context or removal line not verbatim in the source → refuses `context_mismatch` (US4 scenario 3)
- [X] T038 [P] [US4] Test in `tests/unit/test_patch_reconstruct.py`: a block naming a file absent from the target → refuses `file_not_found`
- [X] T039 [P] [US4] Test in `tests/unit/test_patch_reconstruct.py`: a two-hunk block where ONE hunk refuses → the WHOLE fix refuses; no partial patch is returned (FR-012)
- [X] T040 [P] [US4] Test in `tests/integration/test_poc_runner_loop.py`: a reconstruction refusal → `passed_unchecked` with reason `reconstruction_refused`; never `passed_verified`, never a failure (US4 scenario 4)

### Implementation for User Story 4

- [X] T041 [US4] Add `ReconstructionRefused(Exception)` carrying a reason to `scripts/patch_reconstruct.py`, raised from `locate_anchor`/`reconstruct` for `anchor_not_found`, `anchor_ambiguous`, `context_mismatch`, `file_not_found` (FR-009); no fuzzy-match, approximate, re-indent, or best-guess path exists anywhere in the module (FR-010); comment WHY refusal beats a best guess — a wrong `verified` is worse than no signal, because the operator would trust it
- [X] T042 [US4] Enforce all-or-nothing in `reconstruct()` in `scripts/patch_reconstruct.py`: any hunk's refusal aborts the whole fix, returning no partial patch (FR-012)
- [X] T043 [US4] Wire reconstruction into `mutation_verify` in `scripts/poc_queue_runner.py`: when the resolved fix is a report block (`fix`, not `fix_patch`), reconstruct it; on `ReconstructionRefused` return `("unavailable", "reconstruction_refused")` and log the refusal reason

**Checkpoint**: all four stories independently testable; refusal proven for every uncertainty case.

---

## Phase 7: Polish & Cross-Cutting

- [X] T044 Create `tests/architecture/test_verification_no_model.py` asserting the verification path performs NO model call — `scripts/patch_reconstruct.py` imports no client and calls no `generate`, and `mutation_verify` reaches no generation client. FR-011 is a principle (a model here destroys the mechanism's reason to exist), and principles in this repo are guarded by a test — `tests/architecture/test_harness_sandbox_only.py` sets the precedent for this exact shape
- [X] T045 Run `pytest tests/unit/test_patch_reconstruct.py tests/architecture/test_verification_no_model.py -q` — pass offline with no model, container, or network (SC-007)
- [X] T046 Run the full suite `pytest -q` and confirm zero regressions, especially `tests/unit/test_poc_queue_runner.py` and `tests/integration/test_poc_runner_loop.py` whose `mutation_verify` contract changed in Phase 2 (FR-013)
- [X] T047 Verify the guards can fail by mutation: make `locate_anchor` return the FIRST match instead of refusing on ambiguity → T036 must FAIL; drop the verbatim check in `reconstruct` → T037 must FAIL; revert the quarantine set in `scripts/poc_queue_runner.py` to `("passed", "compiled")` → T010 must FAIL. Revert all three. A guard that cannot fail is not a guard (SC-003)
- [X] T048 Add a landing entry to `docs/roadmap.md` for spec 025: the trust mechanism ran 0 times in 10 passes across two live runs; the cause (report diffs are illustrations — both tools reject them, proved by running them, not by inference); that `passed` conflated verified with unverifiable; the two traps analysis caught before any code (`unverified_pass` already means the OPPOSITE; quarantine keys on the literal `"passed"`); and the honest ceiling — the report channel reaches at most 3 of 23, the operator channel removes the limit, and 18 of 23 tasks are leads that never carry a report fix
- [X] T049 Correct the spec-022 live-run entry in `docs/roadmap.md`: the recorded milestone "3/5 REAL fork-verified PoCs" overstated the evidence — those proofs ran on a fork but none survived falsification, because falsification never ran. Correct in place, as spec 024 did with its own wrong diagnosis. Sequential after T048 (same file)
- [X] T050 Confirm no audited-target material entered the repo: review `git diff --stat`, verify every fixture name in the new test files is invented, and `pytest tests/architecture/test_no_target_material.py -q` passes

---

## Dependencies & Execution Order

```
Phase 1 Setup (T001)
   └─> Phase 2 Foundational (T002 → T003 → T004, T005)   ← BLOCKS all stories
          ├─> Phase 3 US1 (T006–T010 → T011 → T012 → T013 → T014)
          │      └─> Phase 4 US2 (T015–T020 → T021 → T022 → T023)
          └─> Phase 5 US3 (T024 → T025–T029 → T030 → T031 → T032 → T033)
                 └─> Phase 6 US4 (T034–T040 → T041 → T042 → T043)
                        └─> Phase 7 Polish (T044 → T045 → T046 → T047, T048 → T049, T050)
```

- **Phase 2 blocks everything**: the reason must reach the caller before any outcome can state it.
- **US1 → US2**: US2's `patch_failed`/`no_fix` outcomes are expressed in the vocabulary US1 introduces.
- **US3 → US4**: same module; US4 adds the refusal taxonomy to functions US3 creates. One unit of work
  split by the spec's priorities, not independently landable.
- **US1/US2 ∥ US3/US4**: different production files (`poc_queue_runner.py` vs `patch_reconstruct.py`) —
  genuinely parallel until **T043**, the join where reconstruction is called from the runner.
- **T040 needs both branches** (a refusal reason surfacing as an outcome) — it is a US4 test but lands
  after T043 wires them.
- **T048 → T049**: same file, sequential.

## Parallel Opportunities

- **T006–T009**, **T015–T020**, **T025–T029**, **T034–T039** — [P] within each group once that group's
  fixture/harness exists; independent test functions.
- **The US1/US2 branch and the US3/US4 branch** proceed in parallel — no shared production file until T043.
- T048 and T049 are NOT parallel (both edit `docs/roadmap.md`).

## Implementation Strategy

**MVP = Phase 1 + Phase 2 + Phase 3 (US1)**. This alone stops the live misreport: every run to date has
told the operator `passed` for proofs that were never checked. Cheapest phase, highest honesty return;
ship it even if nothing else lands.

**Increment 2 = Phase 4 (US2)** — removes the ceiling. The one that makes verification actually
*reachable* for the 18 leads, where an unverified pass is most dangerous.

**Increment 3 = Phases 5+6 (US3/US4)** — makes the report's own fixes free to use, for the minority that
have one. Lowest coverage, zero marginal operator cost once built.

**Total**: 50 tasks — 1 setup, 4 foundational, 9 US1, 9 US2, 10 US3, 10 US4, 7 polish.
