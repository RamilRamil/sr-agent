# Tasks: Extract the Deterministic Solidity Compile-Fixer Layer

**Feature**: `033-extract-solidity-fixers` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: a behavior-preserving refactor in FOUR independently-green commits (FR-013). New modules
`scripts/solidity_utils.py` + `scripts/solidity_fixers.py`; five named sequence-functions; a temporary
CAPTURED differential test (FR-014); an architecture site-inventory test (FR-009). Oracle = the full
existing suite passing UNCHANGED at EVERY commit + new characterization tests.

**HARD ordering (FR-013)**: each Phase = one commit, GREEN before it lands. The riskiest step (extract,
Phase 2) is gated by the differential test (FR-014); its inline side is CAPTURED from the real loop,
NEVER transcribed. `git checkout` is safe here ONLY on committed code — within a phase use reverse Edit.

**No target material**: fixtures are invented/synthetic forge shapes (`test_no_target_material.py`).

---

## Phase 1: Setup — confirm the dependency inventory (pre-commit)

- [ ] T001 Re-confirm the FR-011 inventory in code before touching anything: `_tracked_sol`,
  `_SKIP_DIRS`, `_path_for`, `POC_SUBDIR` are used by the fixers AND by grounding/index (→ `solidity_utils`);
  `_strip_comments` has NO fixer caller (→ stays in pqr, `_poc_defects` untouched); the fixers' private
  regexes (`_NAMED_IMPORT_RE`, `_UNDECLARED_BLOCK_RE`, `_ADDR_IFACE_LOC_RE`) have no non-fixer caller;
  `_ADDR_IFACE_RE` IS used by `_targeted_hints` (stays in pqr). Note any surprise before proceeding.

---

## Phase 2 = COMMIT 1: extract the five sites into named functions, gated by the CAPTURED differential test (Priority: P1)

**Goal**: the five inline transform sequences become named functions with byte-identical behavior,
proven by a differential test whose inline side is CAPTURED from the real loop. Loops STILL inline.

**Guarantee**: FR-014 differential test (this is the one step no other test covers).

### Implementation

- [ ] T002 [US1] Add five named sequence-functions in `scripts/poc_queue_runner.py` (moved to the fixer
  module in Phase 5), each applying ONE site's EXACT current sequence + per-call args (FR-012):
  `_seq_synth_prewrite(code, project, synth_dir)` = `import_paths(base_dir=synth_dir)`;
  `_seq_synth_repair(code, forge_output, project, synth_dir, symbol_index)` =
  `import_paths(base_dir=synth_dir) → nested → address`;
  `_seq_draft_inplace(code, forge_output, symbol_index, file_map)` = `undeclared → address` (NO
  import_paths — the pinned gap); `_seq_postmodel(code, project, symbol_index, file_map)` =
  `setup_override → import_paths(project) → nested`. Each returns `(code, applied: list[str])`. Do NOT
  change the loops yet.

### Tests (the gate) — MUST be green on the PRE-extraction tree

- [ ] T003 [P] [US2] Characterization tests in `tests/unit/test_solidity_fixers.py`: each named
  sequence-function over a fixed SYNTHETIC forge-output + code fixture asserts the exact output
  (including `_seq_draft_inplace` NOT adding an import path). These are the LASTING guardrail (FR-005).
- [ ] T004 [US1] TEMPORARY differential test (FR-014) in `tests/unit/test_fixer_extraction_diff.py`: for
  each site, obtain the INLINE output by RUNNING THE REAL loop through its existing stub seams and
  READING the artifact it writes (synth: a `run_tests` stub reads `synth_path` at call time — precedent
  `test_synthesize_smoke_uses_relative_import`; drafting: read `write_poc`'s file), and assert it
  byte-equals the named function on the SAME inputs. MUST NOT transcribe the sequence (would agree on a
  mis-copied `base_dir=synth_dir` vs `project`). This file is DELETED in Phase 3.
- [ ] T005 Run `pytest -q` — GREEN on the pre-extraction tree. **COMMIT 1** (extract + tests + gate).

---

## Phase 3 = COMMIT 2: swap the loops to call the named functions, drop the gate (Priority: P1)

**Goal**: the loops call the named functions; no inline sequence remains; the temporary gate is removed.

**Guarantee**: the characterization tests (now pinning) + the existing 031/032 loop-event tests.

### Implementation

- [ ] T006 [US2] In `scripts/poc_queue_runner.py`, replace each loop's inline transform sequence with a
  call to its named function (synth loop ~L916/L962; drafting in-place ~L2613; drafting post-model draft
  ~L2556 and fix ~L2759). Keep each loop's own recompile/bound control flow and the SAME events
  (`postfix_imports`/`scaffold_repair`/`deterministic_fix`, same shape — FR-006).
- [ ] T007 Delete `tests/unit/test_fixer_extraction_diff.py` (its job is done — the characterization
  tests now pin the functions).
- [ ] T008 Run `pytest -q` (esp. the 031 `scaffold_repair` / 032 `deterministic_fix` / import-path
  tests) — GREEN, no behavior change. **COMMIT 2** (swap + drop gate).

---

## Phase 4 = COMMIT 3: move the shared helpers to `solidity_utils` (Priority: P1)

**Goal**: the shared low-level helpers live in a new module both pqr and the fixers import — no cycle.

**Guarantee**: existing grounding/index/`_poc_defects` tests + the characterization tests.

### Implementation

- [ ] T009 [US1] Create `scripts/solidity_utils.py` and MOVE `_tracked_sol`, `_SKIP_DIRS`, `_path_for`,
  `POC_SUBDIR` (+ any shared regex the inventory confirmed) into it, logic-unchanged. Update EVERY
  importer in `poc_queue_runner.py` (grounding/index/fixer call sites) to import from `solidity_utils`.
  `_strip_comments` STAYS in pqr → `_poc_defects` is NOT touched (FR-011 refinement).
- [ ] T010 Run `pytest -q` — GREEN (grounding/index/`_poc_defects`/characterization unchanged).
  **COMMIT 3** (move shared helpers).

---

## Phase 5 = COMMIT 4: move the fixers to `solidity_fixers`, re-export, add the arch test (Priority: P1)

**Goal**: the fixers + named functions live in the fixer module; pqr re-exports (transitional); the
site inventory is an enforced invariant.

**Guarantee**: the full suite + the new architecture test.

### Implementation

- [ ] T011 [US1] Create `scripts/solidity_fixers.py`; MOVE the five `_fix_*` + their private regexes +
  the five named sequence-functions into it (imports `solidity_utils`). `poc_queue_runner.py` imports
  them and RE-EXPORTS the `_fix_*` + the named functions (FR-002) with a TRANSITIONAL deprecation note +
  a follow-up-to-remove marker (FR-010). Internal callers inside `solidity_fixers` call directly, never
  the pqr re-export.
- [ ] T012 [US1] Verify NO import cycle (SC-009): `python -c "import scripts.solidity_fixers"` and
  `import scripts.solidity_utils` each succeed in isolation; `solidity_fixers` does NOT import
  `poc_queue_runner`.
- [ ] T013 [P] [US2] Architecture test in `tests/architecture/test_fixer_sites.py` (FR-009 + SC-002):
  assert the SET of named sequence-functions BY NAME; that each individual `_fix_*` is called ONLY from
  inside a named sequence-function (no stray fixer call escapes into a new unpinned site); AND — the
  SC-002 structural check — that `scripts/poc_queue_runner.py` source contains NO `def _fix_` body (only
  re-export bindings), so "no fixer logic in pqr" is enforced, not merely "the file got shorter" (a
  re-export would satisfy shortness without it). Key on the name-set, not line numbers.
- [ ] T014 Run `pytest -q` — GREEN (characterization now targets `solidity_fixers`; existing `pqr._fix_*`
  tests pass via re-export). **COMMIT 4** (move fixers + arch test).

---

## Phase 6: Polish & cross-cutting

- [ ] T015 Run the full suite `pytest -q` on the final tree — all pass UNCHANGED (SC-001); confirm zero
  behavior change end-to-end.
- [ ] T016 [P] Confirm the per-commit history satisfies SC-006 (each of the four commits is a reviewable
  no-op diff — extract / swap / move-utils / move-fixers) and SC-007/SC-010 (tests-first, differential
  was green then removed): `git log --stat` over the four commits.
- [ ] T017 [P] Verify the guardrails can fail: break a named function's per-call arg
  (`import_paths(base_dir=synth_dir)` → `import_paths(project)`) → its characterization test FAILS; add a
  stray inline `_fix_*` call in a loop → the FR-009 architecture test FAILS. Revert (reverse Edit).
- [ ] T018 [P] Confirm no target material (`pytest tests/architecture/test_no_target_material.py -q`) and
  that `test_no_target_material` still scans `scripts/*.py` (it will now also cover the two new modules).
- [ ] T019 [P] Add a landing entry to `docs/roadmap.md` for spec 033: the import-path bug class recurred
  3× because the fixers were scattered + two near-duplicate repair loops hand-inlined their sequences;
  the fix extracts the fixers into `solidity_fixers` (+ shared `solidity_utils` to break the cycle) and
  pins each of the five sequences with characterization tests + a name-keyed architecture inventory; a
  pure behavior-preserving no-op in four guarded commits (differential-gated extraction, captured not
  transcribed); the SEQUENCE UNIFICATION is deferred to the 034 stub (measured). Note the 5-round spec
  review that hardened it.

---

## Dependencies & Execution Order

```
Phase 1 (T001) → Phase 2/COMMIT 1 (T002 → T003,T004 → T005)
   → Phase 3/COMMIT 2 (T006 → T007 → T008)
   → Phase 4/COMMIT 3 (T009 → T010)
   → Phase 5/COMMIT 4 (T011 → T012 → T013 → T014)
   → Phase 6 Polish (T015 → T016,T017,T018,T019)
```

- **STRICT phase order** — each commit must be green before the next (FR-013). No skipping.
- **T004 (differential) before T006 (swap)** — the gate must exist and be green before the inline is
  removed; it is deleted in T007.
- **T009 (utils move) before T011 (fixer move)** — the fixer module imports `solidity_utils`.

## Implementation Strategy

**Four commits, each a reviewable no-op.** The value: fixers consolidated (one home → a logic fix
applies everywhere), sequences pinned (characterization), the site inventory enforced (arch test), the
cycle broken (utils module). The sequence UNIFICATION — the behavior change — is explicitly NOT here
(034, measured).

**Total**: 19 tasks — 1 setup, 3 commit-1, 3 commit-2, 2 commit-3, 4 commit-4, 5 polish (2 tests/module
+ mutation + no-target + roadmap).
