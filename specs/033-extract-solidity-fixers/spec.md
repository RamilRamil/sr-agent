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

| Site | Sequence |
|------|----------|
| synthesis pre-write | `import_paths(base_dir=synth_dir)` |
| synthesis repair loop | `import_paths(base_dir=synth_dir) → nested → address_interface` |
| drafting post-model (draft) | `setup_override → import_paths(project) → nested` |
| drafting in-place repair | `undeclared_import → address_interface` |
| drafting post-model (fix) | `setup_override → import_paths(project) → nested` |

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

**Independent test**: Each characterization test drives one site's transform sequence over a fixed forge
output + code and asserts the resulting code; the tests are green on the current (pre-move) behavior and
stay green after the move.

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
  address→interface, auto-import undeclared, setup-override) and the regexes/constants they own MUST
  move, logic-unchanged, into a new dedicated module.
- **FR-002**: Every existing call site — harness AND tests — MUST keep working via import or re-export
  from `poc_queue_runner.py`; no test LOGIC may change.
- **FR-003**: Each fixer's output MUST be byte-identical to before for the same inputs (pure move).
- **FR-004**: The five transform-application sites MUST keep their EXACT current sequences (order,
  per-call args, and which transforms) — this spec does NOT unify or alter any sequence.
- **FR-005**: Characterization tests MUST pin each site's sequence: given a recorded/synthetic forge
  output + input code, the sequence's OUTPUT is asserted — green before and after the move.
- **FR-006**: The run-log events (`postfix_imports`, `scaffold_repair`, `deterministic_fix`) MUST keep
  the same names and field shapes.
- **FR-007**: NO fixer logic, NO sequence, NO error class, NO model call may change; the compile/pass
  verdict, exploit-logic path, `_poc_defects`, fork oracle, `mutation_verify`, and 029 trace feedback
  MUST be untouched.
- **FR-008**: The refactor MUST be validated by the full existing offline suite passing UNCHANGED plus
  the new characterization tests; no forge/model/network in tests; no target material
  (`test_no_target_material.py`).

### Key Entities *(include if feature involves data)*

- **Deterministic transform**: a pure `code → (code, changed)` fixer. Moves module, logic unchanged.
- **Fixer module** (new): the dedicated home for the transforms + their regexes/constants.
- **Transform-application site** (existing ×5): a place a loop applies a specific sequence of transforms.
  Sequences are unchanged; each is now pinned by a characterization test.
- **Characterization test** (new): records one site's sequence output over a fixed forge input — the
  guardrail that makes the future unification safe.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The full existing test suite passes UNCHANGED after the move (no test-logic edits).
- **SC-002**: The fixers live in the new module; `poc_queue_runner.py` shrinks by the moved block.
- **SC-003**: Each of the five sites keeps its exact sequence; a characterization test pins each
  (including the drafting in-place site's ABSENCE of `import_paths`).
- **SC-004**: Each fixer's output is byte-identical to before (existing fixer tests pass as-is).
- **SC-005**: The loop events are unchanged in name and shape (existing 031/032 loop tests pass as-is).
- **SC-006**: `git diff` shows a move + re-export + new tests only — no fixer logic or sequence change
  (reviewable as a pure no-op).

## Assumptions

- The transforms are cohesive pure functions that can move together; they depend only on `_path_for`/
  the index/file-map, which move with them or are passed in.
- Re-exporting moved symbols from `poc_queue_runner.py` is preferred over editing many test import lines
  — keeps the diff a pure move.
- Characterization tests over SYNTHETIC forge outputs (matching the real shapes captured in the run logs)
  are a sufficient guardrail; recording real (sanitized, invented-name) forge shapes is acceptable.
- The five sites' sequence differences are LEFT intact here; whether any should be unified/closed is a
  separate, measured question (deferred to a later spec).

## Out of Scope

- Any UNIFICATION of the transform sequences or the shared "one helper" — deliberately deferred to a
  separate, explicitly-measured spec (034), because it CHANGES behavior and needs its own evidence
  (e.g. does giving the drafting in-place step `import_paths` actually improve compile-convergence?).
- Splitting grounding / drafting / falsification / CLI out of the monolith — a later cut; this spec
  extracts ONLY the deterministic-fixer functions.
- Changing ANY fixer's logic or adding error classes.
- The fuzzing/symbolic hybrid (item "b").
- The fork oracle, `_poc_defects`, `mutation_verify`, the 029 trace feedback, retry/timestamps.
