# Tasks: Harden Scaffold Synthesis with a Deterministic Repair Pass

**Feature**: `031-harden-scaffold-synth` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: all in `scripts/poc_queue_runner.py` — a bounded repair loop around `synthesize_scaffold`'s
smoke build, a new `_fix_address_interface` transform, a new 9553 rule in `_targeted_hints`, a
`SYNTH_REPAIR_ROUNDS` constant, a `scaffold_repair` event; plus tests. No new files.

**Tests ARE requested** — FR-012 makes the offline tests part of the feature. The smoke `run_tests` and
the model call are NEVER run in tests (stubbed). Fixtures are SYNTHETIC (invented contract/interface
names, captured-bad synth source, synthetic 9553 forge errors) — no target material
(`test_no_target_material.py`).

**Story mapping**: US1 (bounded repair loop) needs the loop + the transforms it applies. US2 (9553) is
the transform `_fix_address_interface` (used by the synth loop) PLUS the `_targeted_hints` rule (for the
drafting PoC) — both ship with US1 (the loop has nothing to apply for the observed failure without the
9553 transform). US3 (observability) is the `scaffold_repair` event. US1+US2 are the MVP.

---

## Phase 1: Setup

- [ ] T001 Verify the seams before editing `scripts/poc_queue_runner.py`: confirm (a) `synthesize_scaffold`'s
  smoke write+compile is at ~L888–917 and its `no_build` branch deletes the base + returns None, (b)
  `_fix_import_paths(code, project, base_dir=synth_dir)` is already applied pre-write (~L881) and
  `_fix_nested_type_imports(code, symbol_index, file_map)` exists, and (c) `_targeted_hints` (~L1515+)
  is the shared hint builder and does NOT yet handle solc 9553.

---

## Phase 2: User Story 1 + User Story 2 — bounded deterministic repair + 9553 fix (Priority: P1)

**Goal**: a synthesized base that fails the smoke build on a deterministically-fixable error is
repaired and re-compiled (up to a bounded number of rounds) instead of discarded; the address→interface
(9553) error is one such fix, added as a code transform (synth) and a hint (drafting PoC).

**Independent test**: with the smoke `run_tests` stubbed no_build→compiled and the model stubbed to
fail if called, the repair loop applies a deterministic fix and accepts the now-compiling base; a base
that never compiles is rejected after the bound; `_fix_address_interface` wraps a 9553-flagged arg.

### Tests for US1 + US2

- [ ] T002 [P] [US2] Test in `tests/unit/test_poc_queue_runner.py`: `_fix_address_interface` over a
  SYNTHETIC synth-base + a synthetic 9553 forge error `Invalid implicit conversion from address to
  contract IFoo requested` (pointing at a line `setter(address(x))`) rewrites that line to
  `setter(IFoo(address(x)))`, edits ONLY the flagged line, and is idempotent (re-run = no change)
  (FR-004).
- [ ] T003 [P] [US2] Test in `tests/unit/test_poc_queue_runner.py`: `_fix_address_interface` on forge
  output WITHOUT a 9553 error returns the code unchanged (`changed=False`) (FR-005 specificity).
- [ ] T004 [P] [US2] Test in `tests/unit/test_poc_queue_runner.py`: `_targeted_hints` on a 9553 forge
  output emits an authoritative hint naming `IFoo` and prescribing `IFoo(address(...))`; on output
  without the error, no conversion hint appears (FR-004/FR-005; shared-benefit for the PoC path).
- [ ] T005 [P] [US1] Test in `tests/unit/test_poc_queue_runner.py`: `synthesize_scaffold` with the model
  stubbed to return a base and `run_tests` stubbed to return no_build THEN compiled — the base is
  ACCEPTED (`scaffold_synthesized` emitted, a Path returned) after one repair round; the deterministic
  fix is applied and NO model call is made in the repair (SC-001/SC-005).
- [ ] T006 [P] [US1] Test in `tests/unit/test_poc_queue_runner.py`: `synthesize_scaffold` with
  `run_tests` stubbed to ALWAYS return no_build — the base is rejected after `SYNTH_REPAIR_ROUNDS`
  (`scaffold_synthesis_failed`/`no_build`, returns None), and at most `SYNTH_REPAIR_ROUNDS` smoke builds
  ran (SC-002; bound respected).
- [ ] T007 [P] [US1] Test in `tests/unit/test_poc_queue_runner.py`: `synthesize_scaffold` with
  `run_tests` stubbed to return compiled on the FIRST build — accepted with ZERO repair rounds
  (behavior unchanged, SC-003).

### Implementation for US1 + US2

- [ ] T008 [US2] Add `_fix_address_interface(code: str, forge_output: str) -> tuple[str, bool]` to
  `scripts/poc_queue_runner.py`: for each solc 9553 "Invalid implicit conversion from address to
  contract `<Type>`" in `forge_output`, wrap the flagged argument as `<Type>(address(x))` on the
  pointed-at line only (line-by-line, mirroring `_fix_import_paths` safety); idempotent; `changed=False`
  when no 9553 present.
- [ ] T009 [US2] Add the 9553 rule to `_targeted_hints` in `scripts/poc_queue_runner.py`: when the forge
  output has the address→contract conversion error, append an authoritative hint naming `<Type>` and
  prescribing `<Type>(address(x))` (or the typed variable). Specific — only on the error.
- [ ] T010 [US1] Add `SYNTH_REPAIR_ROUNDS` (module constant, ~2–3) and wrap `synthesize_scaffold`'s
  smoke write+compile in a bounded loop: per round run the smoke `run_tests`; on `_compiled` accept
  (emit `scaffold_synthesized`, return path); else apply the deterministic transforms
  (`_fix_import_paths(base_dir=synth_dir)`, `_fix_nested_type_imports`, `_fix_address_interface(...,
  test.stdout+test.stderr)`); if any CHANGED the code, rewrite `synth_path` and loop; if NO change, stop.
  Give up after the bound → existing `scaffold_synthesis_failed`/`no_build` + unlink (unchanged). Infra
  exception → existing `infra` give-up. Acceptance bar unchanged (FR-003/FR-007/FR-008/FR-011).

**Checkpoint**: US1+US2 independently testable — T002–T007 pass; a synth base survives a repairable error.

---

## Phase 3: User Story 3 — the run log shows the repair pass (Priority: P2)

**Goal**: each repair round and its outcome is visible in the run log.

**Independent test**: a repaired-then-accepted synthesis emits a `scaffold_repair` event per round plus
the accept; an exhausted one shows the rounds plus the give-up.

### Tests for US3

- [ ] T011 [P] [US3] Test in `tests/unit/test_poc_queue_runner.py`: a `synthesize_scaffold` run that
  repairs once then compiles emits a `scaffold_repair` event (round index + which transforms changed the
  code) before `scaffold_synthesized`; an always-no_build run emits `scaffold_repair` per round then
  `scaffold_synthesis_failed` (FR-006).

### Implementation for US3

- [ ] T012 [US3] Emit a `scaffold_repair` event in the loop (`scripts/poc_queue_runner.py`) per repair
  round: `{finding_id, round, fixes: [names of transforms that changed the code]}`. The terminal
  `scaffold_synthesized` / `scaffold_synthesis_failed` events stay as today (FR-006).

**Checkpoint**: US3 testable — T011 passes; a run log records the repair pass.

---

## Phase 4: Polish & cross-cutting

- [ ] T013 Run `pytest tests/unit/test_poc_queue_runner.py -q` — all pass offline; no forge/model/
  container/network (SC-006).
- [ ] T014 Run the full suite `pytest -q` and confirm zero regressions — especially the existing
  `synthesize_scaffold` tests (accept/reject/failure-paths), `_fix_import_paths`, `_targeted_hints`,
  `mutation_verify`, and drafting-loop tests, since `synthesize_scaffold` and `_targeted_hints` changed
  (FR-010, SC-007).
- [ ] T015 [P] Verify the guards fail by mutation (on COMMITTED code — revert each mutant with a reverse
  Edit, NEVER `git checkout` uncommitted work): make the loop give up after round 1 (ignore
  `SYNTH_REPAIR_ROUNDS`) → T005 FAILS; make `_fix_address_interface` a no-op → T002 FAILS; drop the 9553
  rule from `_targeted_hints` → T004 FAILS. Revert all three (SC-001/SC-004).
- [ ] T016 [P] Confirm no target material entered the repo: every fixture (synth source, forge error,
  contract/interface names) is invented; `pytest tests/architecture/test_no_target_material.py -q`
  passes (FR-012).
- [ ] T017 [P] Add a landing entry to `docs/roadmap.md` for spec 031: synthesis was one-shot and died on
  a single mechanical error (live: solc 9553 `address→contract IFoo`); a 0/5 opportunity check showed
  synthesis is genuinely required on the target (030 deferred); fix = a bounded DETERMINISTIC repair loop
  (reuse `_fix_import_paths`/`_fix_nested_type_imports` + a new `_fix_address_interface`, no model calls)
  + a shared `_targeted_hints` 9553 rule; eval designed up front (deterministic unit tier + a live
  synth-compile corroboration); Constitution V strengthened (no new model dependency).

---

## Dependencies & Execution Order

```
Phase 1 Setup (T001)
   └─> Phase 2 US1+US2 (T002–T007 tests → T008 → T009 → T010)
          └─> Phase 3 US3 (T011 → T012)
                 └─> Phase 4 Polish (T013 → T014 → T015, T016, T017)
```

- **T008 (`_fix_address_interface`) before T010** — the loop applies it.
- **T009 (`_targeted_hints` rule) is independent** of the loop (serves the PoC path) — can land in
  parallel with T008/T010, but its test T004 is [P] with the others.
- **T010 (the loop) is the integrating change** — needs T008 present.

## Parallel Opportunities

- **T002–T007** — [P] within the group (independent test functions).
- **T015, T016, T017** — [P]; different files (tests vs `docs/roadmap.md`).

## Implementation Strategy

**MVP = Phase 2 (US1+US2)** — the repair loop + the 9553 transform/hint together ARE the feature: a
synth base survives a repairable mechanical error. US3 (observability) and Polish follow.

**Total**: 17 tasks — 1 setup, 9 US1+US2 (6 tests + 3 impl), 2 US3, 5 polish.
