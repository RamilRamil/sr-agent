# Feature Specification: Extract the Deterministic Solidity Compile-Fixer Layer (honest no-op)

**Feature Branch**: `033-extract-solidity-fixers`

**Created**: 2026-07-23

**Status**: Draft (revised — see "Why this is a pure move, NOT a unification")

**Input**: User description: "Extract the deterministic Solidity compile-fixer layer out of the
poc_queue_runner monolith into its own module — a behavior-preserving refactor."

## Why this is a pure MOVE, not a unification (the tension, resolved)

The original framing coupled two things that CANNOT both hold: "remove the duplication between the
repair loops" AND "zero functional change". The transforms are applied at **five** sites with
**divergent** sequences:

| Site | Sequence (CORRECTED from code during T001 — see note) |
|------|----------|
| synthesis pre-write | `import_paths(base_dir=synth_dir)` (discards `changed`) |
| synthesis repair loop | `import_paths(base_dir=synth_dir) → nested(symbol_index, NO file_map) → address_interface` |
| drafting post-model (draft) | `setup_override(if guard) → import_paths(project) → nested(file_map) → scaffold_base` |
| drafting in-place repair | `undeclared_import → address_interface` |
| drafting post-model (fix) | `setup_override(if guard) → import_paths(project) → nested(file_map) → scaffold_base` (stage=`fix{attempt}`) |

> **T001 CORRECTION (2026-07-23, from the code, ground truth for a byte-identical move)**: the original
> table (and FR-001's fixer list) undercounted. There are **SIX** deterministic fixers, not five —
> `_fix_scaffold_base` is a sixth, part of both post-model sequences (its own test exists). It depends on
> `_scaffold_base_name`, which grounding also uses → a SIXTH shared helper for `solidity_utils`. The
> post-model sites apply FOUR fixers, each emitting its OWN event (`postfix_setup`/`postfix_imports`/
> `postfix_nested_import`/`postfix_scaffold_base`, `setup_override` guarded by `guard`) — not one `applied`
> list. Synth-repair's `nested` is called WITHOUT `file_map` (defaults `""`) — a per-call-arg divergence
> from the post-model `nested(file_map)`, exactly the class FR-014 gates. Everywhere "five" appears below,
> read "six fixers / five sites"; the extraction reproduces these EXACT sequences.

The divergence IS where the bug class lives (the in-place drafting step never runs `import_paths`;
`import_paths` runs with a different base in synthesis). A single shared helper would either
re-duplicate the per-site sequence selection (re-opening the bug) or unify the sequences (a behavior
change for every site). And the existing unit tests check each fixer INDIVIDUALLY — they do NOT pin the
per-site SEQUENCE, which is exactly what a unification would change.

**Resolution (this spec)**: do the honest, verifiable no-op FIRST — MOVE the fixer functions into one
module (so a fixer's logic lives in ONE place; the class of logic bug that recurred is fixed once and
applies to every caller) and ADD CHARACTERIZATION tests that pin each site's sequence. Any UNIFICATION
of the sequences (e.g. closing the in-place `import_paths` gap) is a SEPARATE, explicitly-measured
change (a later spec) — because it changes behavior and must be justified by its own evidence, not
smuggled into a "refactor".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The fixer functions live in one module, behavior unchanged (Priority: P1)

The deterministic transform functions and their regexes/constants move, logic-unchanged, into a new
dedicated module; every call site (and every test) keeps working via import/re-export. A fixer's logic
now lives in ONE place, so a fix to it applies to all callers (the function-level cause of the recurring
import-path bug).

**Why this priority**: The consolidation is the refactor's value — one home per fixer — achievable as a
true no-op.

**Independent test**: The full existing suite passes unchanged; each fixer returns byte-identical output
for the same inputs (it only moved).

**Acceptance Scenarios**:

1. **Given** the move is applied, **When** the full suite runs, **Then** it passes with no test-LOGIC
   edits (an import line may change only if a symbol moved and is not re-exported).
2. **Given** any fixer with the same inputs as before, **When** it runs, **Then** its output is
   byte-identical (unchanged logic, new location).
3. **Given** a test references a moved symbol as `pqr._fix_*`, **When** it runs, **Then** it resolves
   (the symbol is re-exported from `poc_queue_runner.py`).

### User Story 2 - The per-site transform sequences are pinned by characterization tests (Priority: P1)

New characterization tests record each of the five transform-application sites' behavior — given a
recorded/synthetic forge output and input code, they assert the exact sequence's OUTPUT — so the
sequences are captured before any future unification can silently change them.

**Why this priority**: The existing tests pin fixers individually, not the SEQUENCE — the thing a
unification would change. Without these, "behavior-preserving" is unverifiable and the future
unification (034) is unsafe.

**Independent test**: Each characterization test calls one site's named sequence-function (FR-012)
directly over a fixed forge output + code and asserts the resulting code; the tests are green on the
current (pre-move) behavior — the named functions are extracted first, preserving each inline sequence —
and stay green after the fixers move.

**Acceptance Scenarios**:

1. **Given** the synthesis repair sequence (`import_paths(base_dir) → nested → address`) over a
   synthetic forge output, **When** run, **Then** the produced code matches the recorded expected output.
2. **Given** the drafting in-place sequence (`undeclared → address`) over a synthetic forge output,
   **When** run, **Then** the produced code matches the recorded expected output (and NOTABLY does NOT
   apply `import_paths` — the gap is captured, not silently changed).
3. **Given** the drafting post-model sequence (`setup_override → import_paths(project) → nested`),
   **When** run, **Then** the produced code matches the recorded expected output.

### Edge Cases

- **A test imports a moved symbol directly**: works via re-export from `poc_queue_runner.py`; no test
  LOGIC change.
- **Any output/event/verdict differs**: the refactor is wrong — the bar is a byte-identical, test-green
  move; the characterization tests catch a drift.
- **The `import_paths` gap in the in-place drafting step**: it is PRESERVED (and pinned by a
  characterization test) — closing it is a separate measured change, not part of this move.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The deterministic transform functions (import-path/SPDX, nested-type imports,
  address→interface, auto-import undeclared, setup-override, AND scaffold-base — SIX total, T001
  correction) and the regexes/constants they own MUST move, logic-unchanged, into a new dedicated module.
- **FR-002**: Every existing call site — harness AND tests — MUST keep working via import or re-export
  from `poc_queue_runner.py`; no test LOGIC may change.
- **FR-003**: Each fixer's output MUST be byte-identical to before for the same inputs (pure move).
  This is verified INDIRECTLY by the existing per-fixer unit tests (which already assert each fixer's
  output) plus the new characterization tests — NO separate differential harness is intended.
- **FR-004**: The five transform-application sites MUST keep their EXACT current sequences (order,
  per-call args, and which transforms) — this spec does NOT unify or alter any sequence.
- **FR-005**: Characterization tests MUST pin each site's sequence: given a recorded/synthetic forge
  output + input code, the sequence's OUTPUT is asserted.
- **FR-005a (test-first ordering — the crux)**: the characterization tests MUST be authored and
  committed FIRST, GREEN on the PRE-MOVE tree, as a SEPARATE commit BEFORE the move commit. A
  characterization test written during or after the move (or by reading already-moved code)
  characterizes the NEW behavior and proves nothing while looking rigorous. This ordering is what turns
  the spec from "no-op by assertion" into a "verifiable no-op" (and matches the constitution's
  test-first gate for sensitive behavior); SC-006's per-commit diff makes it checkable.
- **FR-006**: The run-log events (`postfix_imports`, `scaffold_repair`, `deterministic_fix`) MUST keep
  the same names and field shapes.
- **FR-007**: NO fixer LOGIC, NO sequence, NO error class, NO model call may change; the compile/pass
  verdict, exploit-logic path, `_poc_defects`, fork oracle, `mutation_verify`, and 029 trace feedback
  MUST be untouched — "untouched" means their LOGIC. The ONLY permitted mechanical touches are: import
  lines that change because a shared helper moved to the utils module (FR-011, e.g. `_poc_defects`'s
  `_strip_comments` import), and the loop bodies replacing an inline sequence with a call to its named
  sequence-function (FR-012). Both are covered by the existing tests staying green.
- **FR-008**: The refactor MUST be validated by the full existing offline suite passing UNCHANGED plus
  the new characterization tests; no forge/model/network in tests; no target material
  (`test_no_target_material.py`).
- **FR-009 (site inventory as an enforced invariant, keyed by NAME)**: an ARCHITECTURE test (under
  `tests/architecture/`) MUST assert the KNOWN SET of named sequence-functions (FR-012) BY NAME — and
  that the individual fixers are called ONLY from inside those functions (no inline fixer call escapes
  into a new unpinned site). Keying on the function-NAME set (not line numbers, which any unrelated
  refactor would break and which would get weakened) makes it a stable STRUCTURAL assertion: adding a
  SIXTH site means adding a named function + updating the asserted set — a conscious, declared change,
  not a silent one that re-opens the bug class (specs 031/032 each added a site within days — a sixth is
  likely). Without this, "five sites" is a comment, not an invariant.
- **FR-010 (re-exports are transitional, not the goal)**: re-exports from `poc_queue_runner.py` keep the
  old call sites working, but they MUST be marked TRANSITIONAL (a deprecation note + a follow-up to
  remove them); INTERNAL callers inside the new module MUST call the module's own functions directly,
  never the pqr re-export. NOTE for future test authors: once fixers are called inside the new module,
  a `monkeypatch.setattr(pqr, "_fix_…")` on a re-exported name would patch a symbol NOBODY calls and
  PASS VACUOUSLY — future tests MUST patch the new module's symbol, not the pqr re-export.
- **FR-011 (dependency inventory + shared-utils module — resolves the boundary BEFORE tasks)**: before
  tasks.md, a dependency inventory of the fixers MUST be produced, and the shared low-level helpers the
  fixers pull in that are ALSO used by grounding/gate/scaffold code (`_tracked_sol`, `_SKIP_DIRS`,
  `_path_for`, `_strip_comments`, and any the inventory surfaces) MUST move into a SHARED low-level utils
  module that BOTH `poc_queue_runner.py` and the new fixer module import — avoiding the circular import.
  This is a SECOND, also-honest, behavior-preserving move bundled here (acknowledged as such, not
  smuggled). It touches `_poc_defects` ONLY at its import line (`_strip_comments` now comes from utils) —
  its LOGIC is unchanged; FR-007's "untouchable" means LOGIC, and this mechanical import update is the
  ONE permitted touch, covered by the existing `_poc_defects` tests staying green.
- **FR-012 (extract each site into a named sequence-function — required for FR-005 to be implementable)**:
  the five transform-application sequences are currently INLINE inside `synthesize_scaffold` and
  `_process_finding`, so a characterization test cannot drive "the sequence" in isolation. Each site MUST
  be extracted into its OWN named function (in the fixer module) that applies that site's EXACT current
  sequence (same transforms, same order, same per-call args); the loops call these named functions. This
  is behavior-preserving and is NOT unification — each site keeps its OWN separate function and sequence
  (merging them is 034). The characterization tests (FR-005) target these named functions directly.
- **FR-013 (FOUR commits, each green, each with its guarantee NAMED — not "two")**: the refactor MUST land
  as an ordered sequence of independently-green commits, because the steps have DIFFERENT guarantees and
  the riskiest one (extracting two of the harness's largest function bodies) is not covered by the
  characterization tests it creates:
  1. **Extract** the five sites into named sequence-functions, gated by FR-014 (loops still run the
     inline sequence). Guarantee: FR-014 differential test.
  2. **Swap** the loops to call the named functions; remove the FR-014 differential test. Guarantee: the
     now-pinning characterization tests + the existing 031/032 loop-event tests.
  3. **Move** the shared low-level helpers to the utils module (FR-011). Guarantee: existing
     grounding/`_poc_defects`/symbol-index tests + the characterization tests.
  4. **Move** the fixers (+ the named sequence-functions) to the fixer module, re-export, add the FR-009
     architecture test. Guarantee: the characterization tests + the full suite.
  SC-006's "diff reviewable as a pure no-op" applies PER COMMIT — a single mega-diff mixing all four is
  NOT reviewable as a no-op and is disallowed.
- **FR-014 (temporary differential gate for the UNPROTECTED extraction step)**: in commit 1, both the
  inline sequence and the extracted named function MUST coexist, and a TEMPORARY differential test —
  authored against the PRE-extraction inline behavior — MUST assert they produce BYTE-IDENTICAL output on
  the same inputs. It is removed in commit 2 once the loop calls the extracted function. This is exactly
  the differential check FR-003 rejects for the fixers (redundant there) — but here it is the ONLY thing
  that gates the extraction, the one step no other test covers.
  - **The inline side MUST be captured by RUNNING THE REAL loop, not transcribed.** The differential
    test MUST obtain the inline output by executing the actual pre-extraction loop
    (`synthesize_scaffold` / `_process_finding`) through its existing stub seams and CAPTURING the
    artifact the loop WRITES (synth: `synth_path.write_text(code)` each round; drafting: `write_poc(...)`)
    — via a `run_tests` stub that reads the written file at call time (working precedent already in the
    repo: `test_synthesize_smoke_uses_relative_import` captures the smoke file exactly this way). It MUST
    NOT re-transcribe the sequence in the test and compare that to the extracted function: that compares
    the extraction to a SECOND transcription (vacuous), and — critically — it would AGREE on a mis-copied
    per-call arg (the class that bites most here: `import_paths(base_dir=synth_dir)` in synthesis vs
    `import_paths(project)` in drafting), greening the gate while the extraction stays wrong. A passing
    check that checks nothing is the same failure `_poc_defects` exists to catch.

### Key Entities *(include if feature involves data)*

- **Deterministic transform**: a pure `code → (code, changed)` fixer. Moves module, logic unchanged.
- **Fixer module** (new): the dedicated home for the transforms + their regexes/constants.
- **Transform-application site** (existing ×5): a place a loop applies a specific sequence of transforms.
  Sequences are unchanged; each is now pinned by a characterization test.
- **Characterization test** (new): records one named sequence-function's output over a fixed forge input
  — the guardrail that makes the future unification safe.
- **Shared low-level utils module** (new, FR-011): the home for helpers the fixers share with grounding/
  gate/scaffold (`_tracked_sol`, `_SKIP_DIRS`, `_path_for`, `_strip_comments`); imported by both
  `poc_queue_runner.py` and the fixer module, breaking the would-be import cycle.
- **Named sequence-function** (new, FR-012): a function per transform-application site applying that
  site's exact sequence; the loops call it and the characterization tests target it (five in total).
- **Temporary differential test** (new, FR-014): the commit-1-only oracle asserting each extracted
  sequence-function is byte-identical to the prior inline behavior; removed in commit 2.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The full existing test suite passes UNCHANGED after the move (no test-logic edits).
- **SC-002**: NO fixer LOGIC remains in `poc_queue_runner.py` — the fixer definitions live in the new
  module; `poc_queue_runner.py` holds at most TRANSITIONAL re-exports (verified structurally: no `def
  _fix_*` bodies in pqr — NOT merely "the file got shorter", which a re-export would satisfy without
  changing coupling).
- **SC-003**: Each of the five sites keeps its exact sequence; a characterization test pins each
  (including the drafting in-place site's ABSENCE of `import_paths`).
- **SC-004**: Each fixer's output is byte-identical to before (existing fixer tests pass as-is).
- **SC-005**: The loop events are unchanged in name and shape (existing 031/032 loop tests pass as-is).
- **SC-006**: `git diff` shows a move + re-export + new tests only — no fixer logic or sequence change
  (reviewable as a pure no-op).
- **SC-007**: The characterization tests land in a SEPARATE commit that is GREEN on the PRE-MOVE tree
  (per-commit history shows tests-first, then the move) — FR-005a.
- **SC-008**: An architecture test asserts the enumerated set of fixer call sites; adding a site fails it
  until the set is consciously updated (FR-009).
- **SC-009 (FR-011 acceptance)**: the shared low-level helpers live in the utils module; BOTH
  `poc_queue_runner.py` and the fixer module import them; there is NO import cycle (verifiable: importing
  each module in isolation succeeds; a static/import check finds no pqr↔fixer-module cycle).
- **SC-010 (FR-012/FR-014 acceptance)**: the named sequence-functions exist — **FOUR** in the
  implementation, not five: `_seq_postmodel` serves BOTH post-model sites (draft & fix), whose sequences
  are byte-identical, so the site-specific `stage` is emitted caller-side (a genuine no-op merge, not the
  spec-034 unification; enforced by name in `tests/architecture/test_fixer_sites.py`) — and the two loops
  call them (no inline fixer sequence remains in `synthesize_scaffold`/`_process_finding`); the commit-1
  differential test was GREEN (byte-identical inline vs extracted) and is removed by commit 2 (per-commit
  history shows it).

## Assumptions

- **CORRECTED (a review found the naive cohesion claim FALSE)**: the fixers are NOT self-contained —
  they share low-level helpers with code FR-007 declares untouchable: `_tracked_sol` and `_SKIP_DIRS`
  are used by the fixers AND by grounding (`_resolve_local_imports`) and symbol-index/file-map building;
  `_path_for` by two fixers; `_strip_comments` by `_poc_defects` and scaffold-state-var analysis. So a
  clean "move only the fixers" is impossible: moving these helpers would drag grounding/gate call sites
  (not a fixer move); leaving them in pqr and importing from the new module creates a CIRCULAR import
  (pqr re-exports fixers from the new module, the new module imports helpers from pqr). The boundary is
  resolved by FR-011 (a shared low-level utils module) — see below.
- Re-exporting moved symbols from `poc_queue_runner.py` keeps the diff a pure move AND the old call
  sites working — but it is TRANSITIONAL (FR-010): the coupling win comes from removing them later, not
  from the re-export itself.
- Characterization tests over SYNTHETIC forge outputs (matching the real shapes captured in the run logs)
  are a sufficient guardrail; recording real (sanitized, invented-name) forge shapes is acceptable.
- The five sites' sequence differences are LEFT intact here; whether any should be unified/closed is a
  separate, measured question (deferred to a later spec).

## Out of Scope

- Any UNIFICATION of the transform sequences or the shared "one helper" — deliberately deferred to
  spec **034** (created as a DEFERRED stub, `specs/034-unify-fixer-sequences/`), because it CHANGES
  behavior and needs its own evidence (its proof-question: does giving the drafting in-place step
  `import_paths` actually improve compile-convergence?).
- Splitting grounding / drafting / falsification / CLI out of the monolith — a later cut. (This spec is
  NOT "only the fixer functions": it also moves the shared low-level helpers to a utils module (FR-011)
  and edits the two loop bodies to call named sequence-functions (FR-012) — all behavior-preserving, but
  the diff legitimately touches the fixer layer, the shared helpers, `_poc_defects`'s import, and both
  loops. The scope boundary is "no LOGIC/sequence change", not "one file".)
- Changing ANY fixer's logic or adding error classes.
- The fuzzing/symbolic hybrid (item "b").
- The fork oracle, `_poc_defects`, `mutation_verify`, the 029 trace feedback, retry/timestamps.
