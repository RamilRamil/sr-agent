# Tasks: Deterministic Compile-Fixers in the Drafting Loop

**Feature**: `032-deterministic-compile-fix` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: all in `scripts/poc_queue_runner.py` — a new `_fix_undeclared_import` transform, a
deterministic error-driven repair step in the drafting loop (reusing it + the existing
`_fix_address_interface`), a `deterministic_fix` event; plus tests. No new files.

**Tests ARE requested** — FR-010 makes the offline tests part of the feature. The model call and forge
subprocess are NEVER run in tests (stubbed). Fixtures are SYNTHETIC (invented contract/interface names,
synthetic forge 7576/7920/9553 errors, a stubbed `file_map`) — no target material
(`test_no_target_material.py`).

**Story mapping**: US1 (auto-import a known symbol) + US2 (never import an unknown — anti-invention) are
the two halves of `_fix_undeclared_import` and ship together. US3 (9553 in the drafting loop) is wiring
the existing transform into the new repair step. US4 (observability) is the `deterministic_fix` event.
US1+US2+US3 are the MVP.

---

## Phase 1: Setup

- [X] T001 Verify the seams before editing `scripts/poc_queue_runner.py`: confirm (a) the drafting loop's
  error-agnostic post-fix pass is `_fix_import_paths(code, args.project)` + `_fix_nested_type_imports`
  at ~L2491 (draft) and ~L2665 (fix), (b) the compile-FALSE repair branch (where the model `fix()` is
  called ~L2644) is where the new deterministic step goes BEFORE `fix()`, (c) `_path_for(file_map,
  name)` (~L1504) resolves a name→path and returns "" for unknown, and (d) `_fix_address_interface`
  (spec 031) is present and takes `(code, forge_output)`.

---

## Phase 2: User Story 1 + User Story 2 — auto-import a known symbol, never an unknown (Priority: P1)

**Goal**: the harness adds the missing import for an undeclared identifier that IS a known project
symbol, and leaves an unknown (typo/invented) name for the model.

**Independent test**: `_fix_undeclared_import` adds `import { Foo } from "<path>"` when a stubbed
file_map resolves `Foo` and forge reports it undeclared; returns the code unchanged when the name is
unknown; is idempotent; is a no-op with an empty file_map.

### Tests for US1 + US2

- [X] T002 [P] [US1] Test in `tests/unit/test_poc_queue_runner.py`: `_fix_undeclared_import` over code
  using `Foo` (unimported) + a stubbed `file_map` mapping `Foo` to a real path + forge output
  "Undeclared identifier `Foo`" adds `import { Foo } from "<path>";` and returns `changed=True` (FR-001).
- [X] T003 [P] [US1] Test: the same with the 7920 wording "Identifier not found `Foo`" also triggers
  the import (both wordings handled — FR-001).
- [X] T004 [P] [US2] Test: forge "Undeclared identifier `Bar`" where the file_map does NOT resolve
  `Bar` → code unchanged, `changed=False` (anti-invention — FR-003).
- [X] T005 [P] [US1] Test: a mix — `Foo` (known) and `Bar` (unknown) both undeclared → only `Foo` is
  imported; `Bar` is left (FR-001/FR-003).
- [X] T006 [P] [US1] Test: idempotent — running `_fix_undeclared_import` again on the now-imported `Foo`
  adds no duplicate (`changed=False`) (FR-002).
- [X] T007 [P] [US1] Test: empty `file_map` (no index) → `_path_for` returns "" → no-op, `changed=False`
  (FR-007).

### Implementation for US1 + US2

- [X] T008 [US1] Add `_fix_undeclared_import(code, forge_output, symbol_index, file_map) -> (code,
  changed)` to `scripts/poc_queue_runner.py`: regex the 7576/7920 "Undeclared identifier `X`" /
  "Identifier not found `X`" names from `forge_output`; for each `X` where `_path_for(file_map, X)`
  resolves to a non-empty path AND `X` is not already imported in `code`, prepend `import { X } from
  "<path>";` (after the pragma). Anti-invention: skip an `X` `_path_for` does NOT resolve. Idempotent.

---

## Phase 3: User Story 3 — the 9553 fix runs in the drafting loop (Priority: P1)

**Goal**: a drafted PoC's address→interface error is repaired deterministically by the harness, keyed
on the failing compile's own output.

**Independent test**: the drafting loop's deterministic repair step, given a compile-FALSE `test` whose
output has a 9553, applies `_fix_address_interface` and skips the model fix.

### Tests for US3

- [X] T009 [P] [US3] Test in `tests/integration/test_poc_runner_loop.py`: drive the loop (model/forge
  seams stubbed: `run_tests` returns compile-FALSE-with-9553 THEN compiled) so an attempt compiles-FALSE
  with a synthetic 9553 on a `setter(address(x))` line; assert the code is deterministically fixed to
  `Type(address(x))`, a `deterministic_fix` event fired, the model `fix()` was NOT called, AND the
  deterministic repair did NOT consume an attempt — the model retains its full remaining budget
  (SC-008): e.g. the finding still reaches the model on a LATER attempt / `attempt` did not advance for
  the deterministic round (FR-004/FR-005/SC-008).

### Implementation for US3

- [X] T010 [US1+US3] Add `DET_REPAIR_ROUNDS` (~2) and a BOUNDED IN-PLACE deterministic-repair sub-step
  in the drafting loop (`scripts/poc_queue_runner.py`, on the compile-FALSE branch, BEFORE the
  `_call_with_retry(... fix ...)` call ~L2644): a `while` up to `DET_REPAIR_ROUNDS` — `blob =
  test.stdout + test.stderr`; `code, c_und = _fix_undeclared_import(code, blob, symbol_index,
  file_map)`; `code, c_iface = _fix_address_interface(code, blob)`; if `c_und or c_iface`: emit
  `deterministic_fix` (finding_id, attempt, fixes), `write_poc`, RE-RUN `run_tests` IN-PLACE (update
  `test`/`compiled`); if now compiled → break; else if no change → break. This does NOT advance the
  `for attempt` counter (does NOT consume a model attempt — A1/SC-008). After the sub-step, if compiled
  the attempt proceeds (real_pass/verdict as today); else the model `fix()` runs as today. Runs on the
  compile-FALSE branch for BOTH the draft (attempt 1) failure and fix rounds. Bounded by
  `DET_REPAIR_ROUNDS` + idempotency ⇒ cannot loop (A2 addressed: `_path_for` single-path resolution is
  the anti-invention gate).

**Checkpoint**: US1–US3 testable — T002–T009 pass; the harness fixes the two mechanical classes itself.

---

## Phase 4: User Story 4 — the run log shows the deterministic repair (Priority: P2)

**Goal**: the `deterministic_fix` event records which fix the harness applied.

**Independent test**: when the deterministic step changes the code, the event names the applied fix(es).

### Tests for US4

- [X] T011 [P] [US4] Test (folded into T009 or separate in `test_poc_runner_loop.py`): the emitted
  `deterministic_fix` event carries `fixes` naming the applied transform(s) (e.g. `undeclared_import` /
  `address_interface`) and the attempt (FR-009).

### Implementation for US4

- [X] T012 [US4] Ensure the `deterministic_fix` event (emitted in T010) includes `{finding_id, attempt,
  fixes: [names]}`; the existing `postfix_imports` / `targeted_hints` events are unchanged (FR-009).

**Checkpoint**: US4 testable — T011 passes; a run log records the harness-side repair.

---

## Phase 5: Polish & cross-cutting

- [X] T013 Run `pytest tests/unit/test_poc_queue_runner.py tests/integration/test_poc_runner_loop.py -q`
  — all pass offline; no forge/model/container/network (SC-006).
- [X] T014 Run the full suite `pytest -q` and confirm zero regressions — especially the existing
  `_fix_import_paths` / `_fix_nested_type_imports` / `_fix_address_interface` / `_targeted_hints` /
  drafting-loop tests, since the loop's repair branch changed (FR-006/FR-008, SC-007).
- [X] T015 [P] Verify the guards fail by mutation (on COMMITTED code — reverse Edit, NEVER `git checkout`
  uncommitted work): make `_fix_undeclared_import` ignore the `_path_for` gate (import any undeclared
  name) → T004 (anti-invention) FAILS; make it a no-op → T002 FAILS; drop the `_fix_address_interface`
  call from the loop step → T009 FAILS. Revert all three (SC-001/SC-002/SC-004).
- [X] T016 [P] Confirm no target material entered the repo: every fixture (names, forge errors, file_map)
  is invented; `pytest tests/architecture/test_no_target_material.py -q` passes (FR-010).
- [X] T017 [P] Add a landing entry to `docs/roadmap.md` for spec 032: measured compile-error frequency
  (undeclared ×8, 9553 ×3 in-scope; wrong-arg/invalid-token/instantiate-interface out) showed the
  compile-fix loop does not converge because it relies on the model; fix = the harness deterministically
  auto-imports a KNOWN undeclared symbol (anti-invention gated on `_path_for`) and wires 031's 9553
  transform into the drafting loop — applied to the FAILING code before the model fix (line-number
  safety), recompiling deterministically and skipping the model call when it resolves; data-grounded
  (eval-first), Constitution V strengthened (fewer model round-trips); the exploit-LOGIC wall (item "b",
  fuzzing/symbolic hybrid) is the separate remaining direction.

---

## Dependencies & Execution Order

```
Phase 1 Setup (T001)
   └─> Phase 2 US1+US2 (T002–T007 tests → T008)
          └─> Phase 3 US3 (T009 → T010)   [T010 reuses T008's _fix_undeclared_import]
                 └─> Phase 4 US4 (T011 → T012)   [folded into T010's event]
                        └─> Phase 5 Polish (T013 → T014 → T015, T016, T017)
```

- **T008 before T010** — the loop step calls `_fix_undeclared_import`.
- **T010 integrates** `_fix_undeclared_import` + `_fix_address_interface` + the `deterministic_fix`
  event (US1/US3/US4 all land in this one loop-step change).

## Parallel Opportunities

- **T002–T007** — [P] within the group (independent test functions).
- **T015, T016, T017** — [P]; different files (tests vs `docs/roadmap.md`).

## Implementation Strategy

**MVP = Phase 2 + Phase 3** — `_fix_undeclared_import` (the dominant ×8 class) + the loop step wiring it
and the ×3 9553 transform. US4 (observability) + Polish follow.

**Total**: 17 tasks — 1 setup, 7 US1+US2, 2 US3, 2 US4, 5 polish.
