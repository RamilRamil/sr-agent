# Tasks: Inherited-Base Repair Guards

**Feature**: `024-identifier-collision-guard` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: one production file (`scripts/poc_queue_runner.py`) + two new test files. No new
dependencies, no kernel/pack changes, fully offline.

**Tests ARE requested** — FR-013 makes offline deterministic tests part of the feature, so each story
writes its tests before its implementation.

**Test layout** follows the repo's established per-error-code convention (`test_targeted_hints_2904.py`):
one file per error code, so each entry's regression guards live beside the entry they protect (FR-014).

**Fixture rule (non-negotiable, every test task)**: fixtures are **invented** and reproduce only the
SHAPE of compiler output. No name, path, or contract identifier from any audited target enters this
repo (memory `feedback_no_target_code_in_agent`). The live log grounds the design; it stays outside.

---

## Phase 1: Setup

- [X] T001 [P] Create `tests/unit/test_targeted_hints_9097.py` with a docstring naming feature 024 US1/US2 and the offline/synthetic-fixture contract, importing `_targeted_hints` from `scripts.poc_queue_runner` — no environment guard (the sibling `test_targeted_hints_2904.py` proves the import is side-effect-free)
- [X] T002 [P] Create `tests/unit/test_targeted_hints_9582.py` with a docstring naming feature 024 US3, stating that its byte-identical assertions are the regression guard on the one pre-existing entry this feature touches

---

## Phase 2: Foundational (blocking prerequisites for US1 and US3)

**Purpose**: the shared parsing primitive and the evidence channel both stories need. No user-visible
behavior changes in this phase.

- [X] T003 Add module-level `_BASE_STATE_VAR_RE` to `scripts/poc_queue_runner.py` beside the existing `_STATE_VAR_TYPE_RE` (~line 747), matching `<type> <visibility> <name>;` with `\w+` for the type (NO casing assumption — live trap: `sNUSDAprPairProvider internal provider;`) and capturing the NAME; comment WHY it coexists with `_STATE_VAR_TYPE_RE` (that one captures the TYPE, answers a different question)
- [X] T004 Add `scaffold: str = ""` parameter to `_targeted_hints` in `scripts/poc_queue_runner.py` (~line 1416) with a default that preserves today's behavior for every existing caller, and pass `scaffold` from the `_process_finding` call site (~line 2220) where it is already in scope
- [X] T005 Add a back-compat test to `tests/unit/test_targeted_hints_9582.py` asserting `_targeted_hints` called WITHOUT the new `scaffold` argument returns today's output for a 9582 block, byte-identical (pins the default as behavior-preserving; mirrors `test_no_index_no_nested_hint` in the 2904 sibling)

**Checkpoint**: primitive + evidence channel exist; no behavior has changed yet.

---

## Phase 3: User Story 1 — Redeclaration collision repaired in one shot (Priority: P1)

**Goal**: `Identifier already declared` yields an authoritative, identifier-named instruction not to
redeclare what the base declares.

**Independent test**: feed a synthetic 9097 block naming a concrete identifier → guidance names it and
instructs against redeclaration.

### Tests for User Story 1

- [X] T006 [US1] Add fixture builder `_redecl_block(name, base_type, poc_type, base_file, poc_file)` to `tests/unit/test_targeted_hints_9097.py`, producing a realistic `Error (9097): Identifier already declared.` block — primary pointer, `Note: The previous declaration is here:`, and both underlined source lines — with invented names only
- [X] T007 [P] [US1] Test in `tests/unit/test_targeted_hints_9097.py`: a 9097 block naming a concrete identifier → hint fires and the returned text contains that identifier (US1 scenario 1)
- [X] T008 [P] [US1] Test in `tests/unit/test_targeted_hints_9097.py`: a 9097 block whose declaration TYPE starts lowercase → identifier still extracted (live trap A; would fail under `_STATE_VAR_TYPE_RE`'s `[A-Z]`)
- [X] T009 [P] [US1] Test in `tests/unit/test_targeted_hints_9097.py`: a 9097 block whose two declarations have DIFFERENT types → guidance offers BOTH routes (use inherited / rename), since "use the inherited one" may not typecheck (live trap B, FR-002)
- [X] T010 [P] [US1] Test in `tests/unit/test_targeted_hints_9097.py`: a 9097 block naming two files, one under the PoC directory → the hint names the OTHER file as the declaring location and never points the model at its own file (FR-003)
- [X] T011 [P] [US1] Test in `tests/unit/test_targeted_hints_9097.py`: a 9097 block from which no declaring location is derivable → the hint still fires, without a location (FR-003 graceful degradation)
- [X] T012 [P] [US1] Test in `tests/unit/test_targeted_hints_9097.py`: a 9097 block whose declaration lines are not confidently parseable → generic-but-correct guidance returned and NO invented identifier name appears (FR-004)

### Implementation for User Story 1

- [X] T013 [US1] Add the redeclaration hint entry to `_targeted_hints` in `scripts/poc_queue_runner.py`, keyed on the literal message text `Identifier already declared` (NOT a numeric code — comment records the observed `9097`, that the originally-assumed `2333` was wrong, and why text-matching is the rule: research Decision 1); place it alongside the existing entries so the shared `dict.fromkeys` de-duplication applies unchanged
- [X] T014 [US1] Implement identifier extraction inside the entry in `scripts/poc_queue_runner.py`: scope to the error block, apply `_BASE_STATE_VAR_RE` to the underlined source lines, take the name both blocks agree on; on no confident parse fall through to the generic instruction (FR-004)
- [X] T015 [US1] Implement declaring-location extraction in `scripts/poc_queue_runner.py`: take the `--> file:line:col` paths from the error block and select the one NOT under `POC_SUBDIR` as the base's; comment WHY `_scaffold_base_name` is not used here (it is per-file by contract, but `_targeted_hints` receives `read_scaffold`'s multi-file blob → would name the wrong base — research Decision 7)
- [X] T016 [US1] Compose the instruction text in `scripts/poc_queue_runner.py`: name the identifier, state the inherited base already declares it, name the declaring location when available, and offer BOTH routes (use the inherited one, or rename if a genuinely distinct variable is intended)

**Checkpoint**: US1 independently testable — T007–T012 pass.

---

## Phase 4: User Story 2 — The guard never fires on unrelated errors (Priority: P1)

**Goal**: conservative, signature-exact firing; every other repair path untouched.

**Independent test**: feed a 7920 block and clean output → the redeclaration guidance is absent and
pre-existing guidance is intact.

**Note**: US2 has NO separate implementation task. It is a property of the matcher T013 introduces —
the full phrase `Identifier already declared` cannot occur inside `Identifier not found` or any other
message, and de-duplication flows through the existing return path. These tests are what make that
property real and keep it true.

### Tests for User Story 2

- [X] T017 [P] [US2] Test in `tests/unit/test_targeted_hints_9097.py`: a 7920 `Identifier not found` block → the redeclaration guidance is ABSENT and the existing undeclared-identifier guidance is still present (US2 scenario 1 — guards against the substring `Identifier` cross-matching)
- [X] T018 [P] [US2] Test in `tests/unit/test_targeted_hints_9097.py`: clean output with no relevant error → no redeclaration guidance (US2 scenario 2)
- [X] T019 [P] [US2] Test in `tests/unit/test_targeted_hints_9097.py`: output containing two identical redeclaration triggers → the guidance appears exactly once, consistent with the layer's existing `dict.fromkeys` de-duplication (US2 scenario 3, FR-012)
- [X] T020 [P] [US2] Test in `tests/unit/test_targeted_hints_9097.py`: output mixing a 9097 block with 6275/9582 blocks → the redeclaration guidance is ADDED alongside the others and none of them is removed or altered (edge case: co-occurring errors)

**Checkpoint**: US2 independently testable — T017–T020 pass; US1 tests still green.

---

## Phase 5: User Story 3 — Real base state variable reached via a wrong qualifier (Priority: P1)

**Goal**: when the scaffold confirms the missing "member" is its own state variable, instruct
unqualified direct use instead of misdirecting to the wrong contract's function list.

**Independent test**: a 9582 error for a name the synthetic scaffold declares → refined guidance;
for a name it does not declare → today's text byte-identical.

### Tests for User Story 3

- [X] T021 [US3] Add fixture builders `_member_block(member, contract)` (a realistic `Error (9582): Member "X" not found or not visible after argument-dependent lookup in contract Y.` block) and `_scaffold(decls)` (synthetic scaffold source) to `tests/unit/test_targeted_hints_9582.py` — invented names only
- [X] T022 [P] [US3] Test in `tests/unit/test_targeted_hints_9582.py`: a 9582 error where the synthetic scaffold declares the member name as a state variable → guidance identifies it as the inherited base's own state variable and instructs direct use without the `Y.` qualifier (US3 scenario 1, FR-008)
- [X] T023 [P] [US3] Test in `tests/unit/test_targeted_hints_9582.py`: same error where the name appears in the scaffold ONLY inside a comment → the refinement does NOT fire (commented-out source is not evidence, FR-008)
- [X] T024 [P] [US3] Test in `tests/unit/test_targeted_hints_9582.py`: same error where the scaffold does NOT declare the name → the pre-existing "no member — use its real functions" text is returned BYTE-IDENTICAL to today's output (US3 scenario 2, FR-009) — the regression guard on the touched entry
- [X] T025 [P] [US3] Test in `tests/unit/test_targeted_hints_9582.py`: same error with an empty scaffold supplied → pre-existing text returned byte-identical (US3 scenario 3, FR-009)

### Implementation for User Story 3

- [X] T026 [US3] In `_targeted_hints`'s existing member-not-found loop in `scripts/poc_queue_runner.py`, add a positive-evidence gate BEFORE today's text: run the existing `_strip_comments` (~line 1300) over `scaffold`, then use `_BASE_STATE_VAR_RE` to test whether the missing member's name is declared there as a state variable (research Decision 8 — `_scaffold_base_name` strips, `scaffold_missing_types` does not; we follow the former because this gate must not misfire)
- [X] T027 [US3] When the gate confirms, emit the refined instruction in `scripts/poc_queue_runner.py`: the name is the inherited base's own state variable (already declared and deployed) — reference it directly, dropping the `Y.` qualifier; leave the `else` branch's existing text completely untouched so FR-009's byte-identical guarantee holds
- [X] T028 [US3] Comment the entry in `scripts/poc_queue_runner.py` with WHY the refinement exists (live finding-2: the PoC reached a REAL base state variable through a wrong qualifier; the old hint sent the model hunting the wrong contract's function list and burned two attempts), WHY it is gated on positive evidence only, and WHY there is no ambiguity suppression (the 9582 error's own precondition is that the compiler already ruled the qualified access out) — using a synthetic paraphrase, no target identifiers

**Checkpoint**: all three stories independently testable; every story's tests green.

---

## Phase 6: Polish & Cross-Cutting

- [X] T029 Run `pytest tests/unit/test_targeted_hints_9097.py tests/unit/test_targeted_hints_9582.py -q` and confirm all US1/US2/US3 tests pass offline with no model, Docker, or network (SC-004)
- [X] T030 Run the full suite `pytest -q` and confirm zero regressions — especially `tests/unit/test_targeted_hints_2904.py`, `tests/unit/test_poc_queue_runner.py` and `tests/unit/test_setup_revert_hints.py`, which exercise the same hint layer (FR-010)
- [X] T031 [P] Verify the anti-inflation property by mutation: temporarily break the text match (e.g. to the wrong code `2333`) and confirm the US1 tests FAIL; temporarily drop the scaffold gate and confirm T024/T025 FAIL; temporarily drop `_strip_comments` and confirm T023 FAILS — then revert all three. A guard that cannot fail is not a guard (SC-006)
- [X] T032 [P] Add a landing entry to `docs/roadmap.md` for spec 024 recording the two corrections the live log forced (error code is 9097 not 2333 → match message TEXT, never codes; the supposed "invented API" was a real base state var reached via a wrong qualifier → both live failures were harness gaps, not model-capability limits, so the paid stronger-model escalation was never needed) and the near-miss caught in analysis (`_scaffold_base_name` is per-file by contract; applying it to `read_scaffold`'s multi-file blob would have named the wrong base)
- [X] T033 Confirm no audited-target material entered the repo: review `git diff --stat`, and verify every fixture name in both new test files is invented (FR-013 fixture rule)

---

## Dependencies & Execution Order

```
Phase 1 (T001, T002)
   └─> Phase 2 Foundational (T003, T004 → T005)          ← BLOCKS all stories
          ├─> Phase 3 US1 (T006 → T007–T012 → T013 → T014, T015 → T016)
          │      └─> Phase 4 US2 (T017–T020)               ← pins US1's matcher, no impl
          └─> Phase 5 US3 (T021 → T022–T025 → T026 → T027 → T028)
                 └─> Phase 6 Polish (T029 → T030 → T031, T032, T033)
```

- **T003 blocks everything**: both US1 (extract the collided name) and US3 (test the scaffold) use `_BASE_STATE_VAR_RE`.
- **T004 blocks US3** (the scaffold must reach the layer). It does NOT block US1 — after remediation A1, US1's declaring location comes from the compiler's own output, not the scaffold.
- **US1 → US2**: US2 pins the matcher US1 introduces; it cannot precede it.
- **US1 ∥ US3**: independent after Phase 2 — different entries, no shared state. They touch the same file, so land them sequentially even though they don't logically depend on each other.
- **T013–T016 and T026–T028** are sequential within their story — same function, same file.

## Parallel Opportunities

- **T001, T002** — [P]; two different new files.
- **T007–T012** (US1 tests) — [P] after T006's fixture builder exists; independent test functions.
- **T017–T020** (US2 tests) — [P].
- **T022–T025** (US3 tests) — [P] after T021's fixture builders exist.
- **T031, T032** — [P]; different files (test files vs `docs/roadmap.md`).

## Implementation Strategy

**MVP = Phase 1 + Phase 2 + Phase 3 (US1)**. That alone fixes live finding-5, which burned 3/3
attempts on an error with no hint at all — the single largest observed waste.

**Increment 2 = Phase 4 (US2)** — makes the new matcher trustworthy (it cannot misfire).

**Increment 3 = Phase 5 (US3)** — fixes live finding-2 by removing the misdirection that consumed its
last two attempts. Independently valuable and independently revertible if the gate ever proves noisy.

**Total**: 33 tasks — 2 setup, 3 foundational, 11 US1, 4 US2, 8 US3, 5 polish.
