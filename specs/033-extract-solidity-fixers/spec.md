# Feature Specification: Extract the Deterministic Solidity Compile-Fixer Layer

**Feature Branch**: `033-extract-solidity-fixers`

**Created**: 2026-07-23

**Status**: Draft

**Input**: User description: "Extract the deterministic Solidity compile-fixer layer out of the
poc_queue_runner monolith into its own module, and route both repair loops through one shared
transform-application helper — a behavior-preserving refactor."

## User Scenarios & Testing *(mandatory)*

This is a **behavior-preserving refactor**. The harness's deterministic compile-fixers (import-path
depth, nested-type imports, address→interface, auto-import undeclared, setup-override) currently live
scattered through the ~3040-line `poc_queue_runner.py`, and TWO near-duplicate deterministic-repair
loops (scaffold-synthesis, spec 031; drafting-loop in-place repair, spec 032) each hand-inline their
own transform sequence. Because of this fragmentation the SAME bug class — relative import-path
resolution — surfaced THREE times in one day (029 smoke-import, 031 synth-base `../` depth, 032
wiring), and the duplicate loops caused a mutation-test to target the wrong loop. This refactor moves
the fixer layer into its own module and routes both loops through ONE shared transform-application
helper — removing the duplication that keeps re-introducing the bug class — with ZERO functional change.

### User Story 1 - The fixer layer lives in its own module (Priority: P1)

The deterministic transform functions and their regexes/constants move, byte-for-byte, into a new
module; every existing call site (including tests referencing them) keeps working via import/re-export.

**Why this priority**: This is the refactor. Consolidating the scattered fixers into one cohesive module
is what removes the fragmentation that caused the recurring bug.

**Independent test**: The full existing test suite passes unchanged — every test that references a
`_fix_*` transform still resolves it (moved + re-exported), and every fixer produces byte-identical
output to before.

**Acceptance Scenarios**:

1. **Given** the refactor is applied, **When** the full test suite runs, **Then** it passes with no
   test-logic edits (at most an import line if a symbol moved and is not re-exported).
2. **Given** any fixer is called with the same inputs as before the move, **When** it runs, **Then** it
   returns byte-identical output (the logic is unchanged — it only moved).

### User Story 2 - Both repair loops share one transform-application helper (Priority: P1)

A single helper runs the deterministic transforms and reports which changed the code; both repair loops
(synthesis and drafting) call it instead of hand-inlining their own transform sequences. Each loop keeps
its own recompile/bound control flow.

**Why this priority**: The duplicated transform-application is the specific thing that let the bug class
recur and made a mutation-test target the wrong loop. Unifying it is the point of the refactor.

**Independent test**: The existing tests for both loops (031 `scaffold_repair`, 032 `deterministic_fix`,
import-path fixes) pass unchanged — both loops still apply the same transforms and emit the same events.

**Acceptance Scenarios**:

1. **Given** a compile error the synthesis loop can fix deterministically, **When** it runs, **Then** it
   applies the transforms via the shared helper and emits the same `scaffold_repair` event as before.
2. **Given** a compile error the drafting loop can fix deterministically, **When** it runs, **Then** it
   applies the transforms via the shared helper and emits the same `deterministic_fix` event as before.
3. **Given** the shared helper, **When** a caller passes only the args relevant to it (synthesis: the
   base dir; drafting: the index + file-map), **Then** the transforms behave identically to the prior
   hand-inlined sequences (same transforms, same order, same output).

### Edge Cases

- **A test imports a moved symbol directly** (e.g. `pqr._fix_import_paths`): it keeps working because
  the symbol is re-exported from `poc_queue_runner.py` (or the test's import line is updated) — no test
  LOGIC changes.
- **A transform that is only relevant to one loop** (e.g. auto-import needs the file-map; the synth loop
  passes none): the shared helper skips a transform whose required inputs are absent, so each loop gets
  exactly the transforms it did before — no new behavior.
- **Event shape**: `postfix_imports` / `scaffold_repair` / `deterministic_fix` events keep the same
  names and fields — downstream log consumers and the proof-eval funnel see no change.
- **No behavior may change**: if any output, event, or verdict would differ, the refactor is wrong —
  the acceptance bar is a byte-identical, test-green move.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The deterministic transform functions (import-path/SPDX, nested-type imports,
  address→interface, auto-import undeclared, setup-override) and the regexes/constants they own MUST
  move, logic-unchanged, into a new dedicated module.
- **FR-002**: Every existing call site — harness code AND tests — MUST keep working, via import or
  re-export from `poc_queue_runner.py`; no test LOGIC may change (an import line may, only if a symbol
  moved and is not re-exported).
- **FR-003**: A single shared helper MUST run the deterministic transforms and report which changed the
  code; it MUST be the ONLY place the transform-application happens for both repair loops.
- **FR-004**: Both repair loops (synthesis, drafting) MUST call the shared helper for their transform-
  application step, replacing their hand-inlined transform sequences; each loop KEEPS its own
  recompile/bound control flow (they differ legitimately and are out of scope to unify).
- **FR-005**: The transforms applied, their order, and their output MUST be identical to before for each
  loop (the helper takes the union; each caller passes only its relevant inputs, and a transform whose
  inputs are absent is skipped — reproducing the prior per-loop sequence exactly).
- **FR-006**: The run-log events (`postfix_imports`, `scaffold_repair`, `deterministic_fix`) MUST keep
  the same names and field shapes.
- **FR-007**: NO fixer logic may change; NO new error class, deterministic behavior, or model call may
  be added; the compile/pass verdict, exploit-logic path, `_poc_defects`, fork oracle, `mutation_verify`,
  and 029 trace feedback MUST be untouched.
- **FR-008**: The refactor MUST be validated by the full existing offline test suite passing UNCHANGED,
  plus the focused loop-event tests (031/032) passing as-is; no forge/model/network in tests.

### Key Entities *(include if feature involves data)*

- **Deterministic transform**: a pure `code → (code, changed)` fixer (import-path, nested-type,
  address→interface, undeclared-import, setup-override). Moves module unchanged.
- **Fixer module** (new): the dedicated home for the transforms + their regexes/constants + the shared
  application helper.
- **Shared application helper** (new): runs the transforms over `code` given a forge output + the
  relevant resolution inputs, returns `(code, applied)`; the single transform-application site for both
  loops.
- **Repair loop** (existing ×2): synthesis (bounded rounds, accept-on-compile, writes the synth file)
  and drafting (in-place recompile within an attempt) — control flow unchanged; only their transform-
  application is now the shared helper.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The full existing test suite (~698 tests) passes UNCHANGED after the refactor — no test
  logic edits.
- **SC-002**: The deterministic transforms live in the new module; `poc_queue_runner.py` shrinks by the
  moved block (a measurable line-count reduction).
- **SC-003**: Both repair loops apply transforms via the single shared helper (no hand-inlined transform
  sequence remains in either loop).
- **SC-004**: Each fixer's output is byte-identical to before for the same inputs (verified by the
  existing fixer tests passing as-is).
- **SC-005**: The loop events (`postfix_imports`, `scaffold_repair`, `deterministic_fix`) are unchanged
  in name and shape (verified by the existing 031/032 loop tests passing as-is).
- **SC-006**: `git diff` shows moves + call-site swaps only — no fixer logic change (reviewable as a pure
  refactor).

## Assumptions

- The listed transforms are cohesive and self-contained enough to move together (they are pure
  string→string functions plus their own regexes; they depend only on `_path_for`/the index/file-map,
  which move with them or are passed in).
- Re-exporting moved symbols from `poc_queue_runner.py` is acceptable and preferred over editing many
  test import lines — keeps the diff a pure move.
- The two loops' control-flow differences (bounded-rounds-writing-synth-file vs in-place-recompile) are
  legitimate and stay; only the transform-application is shared.
- A pure refactor needs no new tests beyond the existing suite as the oracle; a small focused assertion
  MAY be added that both loops route through the shared helper, but the primary guarantee is the
  unchanged suite.

## Out of Scope

- Splitting grounding / drafting / falsification / CLI out of the monolith — a later cut; this spec
  extracts ONLY the deterministic-fixer layer (the piece that caused the recurring bug).
- Changing ANY fixer's logic or adding error classes (import-depth / nested-type / 9553 / 7576-7920 stay
  exactly as they are).
- Unifying the two loops' CONTROL FLOW (bounds / recompile differ legitimately — only the transform-
  application is shared).
- The fuzzing/symbolic hybrid (item "b", the next spec).
- The fork oracle, `_poc_defects`, `mutation_verify`, the 029 trace feedback, and the retry/timestamp
  observability.
