# Implementation Plan: Extract the Deterministic Solidity Compile-Fixer Layer

**Branch**: `033-extract-solidity-fixers` | **Date**: 2026-07-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/033-extract-solidity-fixers/spec.md`

## Summary

A behavior-preserving refactor in FOUR independently-green commits (FR-013): (1) extract the five
inline transform-application sequences into named functions, gated by a temporary CAPTURED differential
test (FR-014); (2) swap the two loops to call them + drop the differential test; (3) move the shared
low-level helpers to a new `solidity_utils` module (breaks the import cycle, FR-011); (4) move the
fixers + named sequence-functions to a new `solidity_fixers` module, re-export from
`poc_queue_runner.py`, add the architecture site-inventory test (FR-009). Oracle: the full existing
suite passes UNCHANGED + new characterization tests pin each sequence.

## Dependency inventory (FR-011 — done here, before tasks)

Verified in code (line refs at plan time):

| Symbol | Used by FIXERS | Also used by (non-fixer) | Placement |
|--------|----------------|--------------------------|-----------|
| `_tracked_sol` (705) | `_fix_import_paths` | 736, 1018, 1216 (grounding/index) | **utils** (shared) |
| `_SKIP_DIRS` (612) | `_fix_import_paths` | 663 grounding, 1029/1039/1173 index | **utils** (shared) |
| `_path_for` (1572) | `_fix_undeclared_import`, `_fix_nested_type_imports` | 1457, 1723 | **utils** (shared) |
| `POC_SUBDIR` | `_fix_import_paths` | many | **utils** (shared const) |
| `_strip_comments` (1501) | **none** | `_poc_defects` 603, grounding 772, scaffold 1639 | **STAYS in pqr** — refinement: no fixer uses it, so `_poc_defects` is NOT touched at all (tighter than FR-007 required) |
| `_scaffold_base_name` (765) | `_fix_scaffold_base` (1482) | grounding 796 | **utils** (shared) — T001 correction: sixth shared helper |
| `_NAMED_IMPORT_RE`, `_UNDECLARED_BLOCK_RE`, `_ADDR_IFACE_LOC_RE` | the fixers | (confirmed none) | **fixers** (private) |
| `_ADDR_IFACE_RE` (1335) | **not the fixer** — `_targeted_hints` (1738) | — | **STAYS in pqr** (hint builder); the fixer uses `_ADDR_IFACE_LOC_RE`, which moves |
| `_fix_scaffold_base` (1475) | itself | drafting post-model 2565/2768 | **fixers** — T001 correction: a SIXTH fixer the original list missed |

**Module boundary**: `solidity_utils` = `_tracked_sol`, `_SKIP_DIRS`, `_path_for`, `POC_SUBDIR` (+ any
shared regex the inventory confirms). `solidity_fixers` = the five `_fix_*` + their private regexes +
the five named sequence-functions; imports from `solidity_utils`. `poc_queue_runner.py` imports both;
re-exports the `_fix_*` (transitional, FR-010). No cycle: fixers→utils, pqr→{utils,fixers}.

## Technical Context

**Language/Version**: Python 3.11+ (`scripts/`).
**Primary Dependencies**: none new. **Storage**: N/A. **Testing**: pytest, offline, deterministic; the
existing suite is the oracle + new characterization/differential/architecture tests. **Project Type**:
single-project CLI harness. **Performance Goals**: N/A (pure refactor). **Constraints**: zero
behavior/sequence change; no import cycle; per-commit reviewable no-op diffs.
**Scale/Scope**: two new modules, five named sequence-functions, three new test kinds (characterization,
temporary differential, architecture inventory), re-exports. No logic change.

## Constitution Check

- **I/II/IV**: unaffected (no trust-boundary, confirmation-gate, or knowledge-promotion change).
- **III. Kernel/Pack Separation**: PASS — new modules live under `scripts/` (harness), no kernel/pack
  contract change.
- **V. No Paid-API Dependency**: PASS — no model/logic change.
- **Test-first gate (dev workflow)**: HONORED explicitly — FR-005a/FR-013/FR-014 require the
  characterization + differential tests to be green on the pre-move/pre-extraction tree, as their own
  commits, before the moves.

**Verdict**: no violations.

## Project Structure

```
scripts/
  solidity_utils.py     # NEW: _tracked_sol, _SKIP_DIRS, _path_for, POC_SUBDIR (shared low-level)
  solidity_fixers.py    # NEW: the five _fix_* + private regexes + five named sequence-functions
  poc_queue_runner.py   # imports both; re-exports _fix_* (transitional); loops call the named funcs
tests/
  unit/test_solidity_fixers.py        # characterization tests for the five named sequence-functions
  unit/test_poc_queue_runner.py       # existing _fix_* tests keep passing (via re-export)
  integration/test_poc_runner_loop.py # existing 031/032 loop-event tests keep passing
  architecture/test_fixer_sites.py    # NEW (FR-009): assert the named-function set + no stray fixer call
```

No `contracts/` (internal refactor). The behavioral contract is the unchanged suite + characterization.

## Approach — the four commits (FR-013)

**Commit 1 — extract sites (gated by the CAPTURED differential test, FR-014)**
- Add five named sequence-functions (in pqr for now, moved in commit 4): each applies ONE site's exact
  current sequence with its exact per-call args, e.g. `_seq_synth_repair(code, forge_output, project,
  synth_dir, symbol_index)` → `import_paths(base_dir=synth_dir) → nested → address`; `_seq_draft_inplace(
  code, forge_output, symbol_index, file_map)` → `undeclared → address`; `_seq_postmodel(code, project,
  symbol_index, file_map)` → `setup_override → import_paths(project) → nested`; plus synth pre-write.
- Loops STILL run their inline sequence. A TEMPORARY differential test CAPTURES the inline output by
  running the REAL loop through its stub seams (synth: reads `synth_path.write_text`; drafting: reads
  `write_poc`) and asserts it byte-equals the named function on the same inputs (FR-014 — captured, never
  transcribed; the class that bites is the per-call base: `base_dir=synth_dir` vs `project`).
- Green on pre-extraction tree.

**Commit 2 — swap + drop the gate**
- Replace each loop's inline sequence with a call to its named function; delete the temporary
  differential test. Now the characterization tests (added here or in commit 1) pin the named functions;
  the existing 031/032 loop-event tests confirm the loops behave identically.

**Commit 3 — move shared helpers to `solidity_utils`**
- Move `_tracked_sol`, `_SKIP_DIRS`, `_path_for`, `POC_SUBDIR`; update every importer (pqr grounding/
  index call sites, the fixers). `_poc_defects` is NOT touched (it uses `_strip_comments`, which stays).
  Protected by existing grounding/index tests + characterization tests.

**Commit 4 — move fixers to `solidity_fixers` + arch test**
- Move the five `_fix_*` + private regexes + the five named sequence-functions into `solidity_fixers`
  (imports `solidity_utils`); `poc_queue_runner.py` imports them and RE-EXPORTS the `_fix_*`
  (transitional, FR-010, with a deprecation note + a follow-up-to-remove marker). Add the architecture
  test (FR-009): assert the set of named sequence-functions by NAME and that the individual fixers are
  called only from inside them. Protected by the full suite.

### Edge handling
- **No import cycle** (SC-009): `solidity_fixers` imports only `solidity_utils`; `pqr` imports both.
  Verify each module imports in isolation.
- **Re-export vacuity trap** (FR-010): internal callers use the module directly; the note warns future
  tests to patch `solidity_fixers._fix_*`, not the pqr re-export.
- **`_ADDR_IFACE_RE` split**: the hint builder `_targeted_hints` (stays in pqr) keeps using it; the
  fixer uses `_ADDR_IFACE_LOC_RE` (moves). Confirm during commit 4; if shared, it goes to utils.

## Complexity Tracking

No constitution violations. The complexity is inherent to the coupling the refactor untangles (a
shared-utils module to break the cycle); it is bounded, staged into four reviewable commits, and
guarded at each step. No entries required.
