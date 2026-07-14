# Tasks: Nested-Type Import Determinism

**Input**: Design documents from `/specs/016-nested-type-import-determinism/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R5), data-model.md,
contracts/nested-import-determinism.md, quickstart.md

**Tests**: INCLUDED and test-first — the no-false-rewrite guarantee and the guard's
idempotency are correctness the harness depends on; each is a failing test before the fix.
Every SC maps to a task. All offline (FR-007).

**Organization**: Setup → Foundational (`nested_container`, shared by all three layers) →
US1 (P1, mechanical guard) → US2 (P1, grounding note) → US3 (P2, 2904 hint). US1/US2/US3 are
independent after Foundational.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files / independent, may run in parallel
- **[Story]**: US1…US3 (Setup/Foundational/Polish carry no story label)

---

## Phase 1: Setup

- [X] T001 Confirm the reusable pieces (no code): the mechanical-guard pattern
  (`_fix_setup_override`/`_fix_import_paths` → `(code, changed)`, applied after draft + every
  fix), `_path_for(file_map, name)` and the file-map format, `_targeted_hints`' signature +
  call site in `_process_finding` (where `symbol_index` is in scope), and `Symbol.contract`
  as the nested flag. Re-confirm no new dependency (FR-007).

**Checkpoint**: the wiring/test targets are confirmed present.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the strict nested-detection predicate all three layers call.

- [X] T002 Add `SymbolIndex.nested_container(name) -> str | None` to
  `scripts/solidity_index.py` (data-model.md): the container iff ≥1 nested struct/enum match
  AND no top-level match AND a single container; else `None`. Write it test-first with
  `tests/unit/test_nested_container.py` (nested → container; top-level → None; ambiguous
  (2 containers) → None; unknown/non-type → None), built via `SymbolIndex.build_from_source`.

**Checkpoint**: the determinism boundary (FR-003) is encoded and tested in one place.

---

## Phase 3: User Story 1 — Mechanical nested-import guard (Priority: P1) 🎯 MVP

**Goal**: a named-import of a known nested type is deterministically rewritten to import the
container; top-level/unknown imports are untouched; idempotent.

**Independent Test**: quickstart.md #1.

### Tests for User Story 1 (write first, expect red)

- [X] T003 [P] [US1] `tests/unit/test_nested_import_guard.py`: `_fix_nested_type_imports` —
  a nested named-import WHERE THE BODY USES THE TYPE BARE (the real case, H1) → the import is
  removed, the container imported, AND the bare uses rewritten to `Container.Type` so the
  result compiles; already-qualified uses (`Container.Type`) left untouched; a mixed line →
  only nested names removed; a top-level/unknown/library import → byte-unchanged
  (`changed=False`); idempotent (second run `changed=False`, identical); an aliased
  `import { X as Y }` → left unchanged (FR-001/FR-003; SC-001/SC-002).

### Implementation for User Story 1

- [X] T004 [US1] Add `_fix_nested_type_imports(code, symbol_index, file_map) -> (code,
  changed)` to `scripts/poc_queue_runner.py` (data-model.md; mirror `_fix_import_paths`
  line-by-line): partition each `import { … } from "…"` into nested (via `nested_container`)
  vs keep; drop nested names (drop the line if none remain); ensure each container is imported
  — path from `_path_for(file_map, container)`, **falling back (L1) to the removed named-import
  line's own path** when the file map lacks it — added only if absent; **then rewrite each
  removed nested type's BARE uses in the body → `Container.Type`** (word-boundary, NOT
  preceded by `.`, skip import lines — H1, required to actually compile); leave
  library/remapped/unknown/aliased imports and already-qualified uses alone. Apply it after
  `draft()` and after every `fix()` alongside the other guards, logging `postfix_nested_import`
  when changed (FR-002/FR-004).

**Checkpoint**: the nested-import error can no longer reach the compiler regardless of the model.

---

## Phase 4: User Story 2 — Nested-reference note in the grounding (Priority: P1)

**Goal**: the proactive struct/enum grounding tells the model how to reference a nested type,
not just its fields.

**Independent Test**: quickstart.md #2.

### Tests for User Story 2 (write first, expect red)

- [X] T005 [P] [US2] Extend `tests/unit/test_struct_grounding.py`: a `callable_api`
  referencing a struct declared inside a contract/interface → `expand_referenced_types`
  output includes the nested-reference note ("nested inside", `Container.Type`, "do not
  named-import"); a top-level referenced type → fields with NO note (FR-005; SC-003).

### Implementation for User Story 2

- [X] T006 [US2] In `expand_referenced_types` (`scripts/solidity_index.py`), for a picked type
  whose `Symbol.contract` is non-empty, append the canonical nested-reference note (identical
  wording to `_render_lookup_response`) after its definition (FR-005).

**Checkpoint**: the model sees fields + correct reference form together, up front.

---

## Phase 5: User Story 3 — Authoritative 2904 hint (Priority: P2)

**Goal**: a nested-type "Declaration not found" compile error yields the exact `Container.X`
fix as an authoritative hint.

**Independent Test**: quickstart.md #3.

### Tests for User Story 3 (write first, expect red)

- [X] T007 [P] [US3] `tests/unit/test_targeted_hints_2904.py`: a synthetic
  `Declaration "X" not found …` where the index knows `X` as nested → an authoritative hint
  naming `Container` and `Container.X`; the same for an unknown/invented name → no
  nested-type hint (FR-006; SC-004).

### Implementation for User Story 3

- [X] T008 [US3] Add a `symbol_index` parameter to `_targeted_hints`
  (`scripts/poc_queue_runner.py`) and a rule: for each `Declaration "(\w+)" not found` in the
  forge output, if `nested_container(X)` resolves, emit the authoritative `Container.X` fix;
  else emit nothing. Update the call site in `_process_finding` to pass `symbol_index`
  (FR-006).

**Checkpoint**: if the model reaches a nested type via a lookup (not the grounding), the
repair hint is authoritative.

---

## Phase 6: Polish & Cross-Cutting

- [X] T009 Run the full offline suite (`tests/unit tests/integration tests/architecture
  tests/security tests/frontend`); confirm all green with the new tests, no new dependency,
  no kernel-invariant test change, and the knowledge-loop tests unaffected (FR-007/FR-008;
  SC-005).
- [X] T010 Update `docs/roadmap.md`: spec 016 landed (deterministic nested-type import fix —
  guard + grounding note + 2904 hint), with the meta-note that the knowledge loop surfaced
  the right lesson yet the model didn't obey, so for a mechanical, index-detectable mistake
  deterministic repair backs the suggestion-only loop.

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002)** → **US1 (T003–T004)** / **US2 (T005–T006)** /
  **US3 (T007–T008)**, which are independent of each other after T002; within each, the test
  precedes the implementation.
- **Polish (T009–T010)** last (needs all three).

### Parallel opportunities

- After T002: T003 (US1 test), T005 (US2 test), T007 (US3 test) are all `[P]` (distinct
  files). The three implementation tracks (T004, T006, T008) can proceed in parallel once
  their tests are red.

---

## Implementation Strategy

### MVP (Setup + Foundational + US1)
The mechanical guard is the model-independent unblocker — it alone gets H-01 past the
nested-import stall. Ship first.

### Then prevention + feedback (US2, US3)
US2 stops the mistake up front in the grounding; US3 makes the repair hint authoritative.
Both additive and independently testable.

### Notes
- Strict determinism boundary: only names `nested_container` resolves are ever touched
  (FR-003) — no false rewrites.
- No kernel invariant / DATA-wrap / trust hierarchy / promotion gate / retrieval change (FR-008).
- Commit per logical group on explicit request (project convention).
