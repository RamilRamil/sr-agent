# Tasks: Live-Run Harness Robustness

**Input**: Design documents from `/specs/015-live-run-harness-robustness/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R5), data-model.md,
contracts/harness-robustness.md, quickstart.md

**Tests**: INCLUDED and test-first — the no-empty-PoC guarantee and the capture-trigger
correctness are behavior the harness's verdicts depend on; each is written as a failing test
before the fix. Every SC maps to a task. All offline (FR-008).

**Organization**: By user story — US1 (P1, clean extraction) → US2 (P1, struct grounding) →
US3 (P2, compile-gated capture). All three are independent (distinct code paths); no shared
foundation beyond the existing harness.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files / independent, may run in parallel
- **[Story]**: US1…US3 (Setup/Polish carry no story label)

---

## Phase 1: Setup

- [X] T001 Confirm the reusable pieces (no code): the spec-009 fake-model/fake-sandbox
  harness in `tests/integration/test_poc_runner_loop.py`; `scripts/solidity_index.py`
  renderers (`_render_struct`/`_render_enum`, `Symbol.definition`) and the index's
  from-sources build path; and the spec-014 `_maybe_capture_lesson` signature +
  its call site in `_process_finding` (where `compiled`/`real_pass` are already computed).
  Re-confirm no new dependency is needed (FR-008).

**Checkpoint**: the wiring/test targets are confirmed present.

---

## Phase 2: User Story 1 — The written PoC is always clean Solidity (Priority: P1) 🎯 MVP

**Goal**: never write prose or an empty file as the PoC; tool-mode empty → marker fallback.

**Independent Test**: quickstart.md #1.

### Tests for User Story 1 (write first, expect red)

- [X] T002 [P] [US1] `tests/unit/test_solidity_extract.py`: `_extract_solidity` on —
  a clean fenced block (byte-identical to today), leading prose + fenced block (prose
  dropped), leading prose + bare Solidity (span from first token), Solidity + trailing prose
  (trailing dropped), and prose-only / empty → `""` (FR-001/FR-002; SC-001).
- [X] T003 [P] [US1] `tests/integration/test_poc_extract_prose.py` (spec-009 fake harness):
  a scripted draft reply with leading prose → the written PoC is clean Solidity; a code-free
  reply → the finding ends a failed draft/fix with **no** `.sol` written (SC-001).
- [X] T004 [P] [US1] `tests/integration/test_tool_empty_fallback.py`: a tool-protocol
  round-trip that returns no Solidity → the finding retries under the marker protocol rather
  than emitting an empty PoC (FR-003/SC-002).

### Implementation for User Story 1

- [X] T005 [US1] In `scripts/poc_queue_runner.py`, add `_extract_solidity(text)` and replace
  `_strip_fences` at every code-extraction site (`draft`, `fix`, `_generate_with_lookups`,
  `_generate_with_tool_calls`, and the synth-scaffold generate). **Span rule (L1, concrete):**
  after taking a fenced block's contents if present, the source is from the first line whose
  stripped form starts with a Solidity token (`// SPDX|pragma|import|contract|interface|
  library|abstract contract`) through the **last line containing `}`** (drop anything after
  the final brace and any leading prose); return `""` when no Solidity token is found. Treat
  `""` as a failed draft/fix (write no file); in the tool path, an empty extraction falls
  back to the marker protocol for that finding (FR-001/FR-002/FR-003).

**Checkpoint**: prose never reaches the `.sol`; no empty/vacuous PoC from code-free replies.

---

## Phase 3: User Story 2 — Struct/enum fields grounded up front (Priority: P1)

**Goal**: the draft prompt shows the fields of struct/enum types the `callable_api`
references, nested one level — so the model stops inventing them (research R2: lookup already
returns fields; the model just constructs before it looks up).

**Independent Test**: quickstart.md #2.

### Tests for User Story 2 (write first, expect red)

- [X] T006 [P] [US2] `tests/unit/test_struct_grounding.py`: build a `SymbolIndex` via
  **`SymbolIndex.build_from_source(src)`** (single source string — the real API; NOT
  `build_from_sources({...})`) over a fixture interface with a struct whose field is another
  struct/enum; assert `expand_referenced_types(callable_api, index)` returns the referenced
  struct's full field list AND the nested type's members (one level), and the enum's values;
  assert the on-demand `_render_lookup_response` still returns fields (no regression)
  (FR-004/FR-005; SC-003).

### Implementation for User Story 2

- [X] T007 [US2] Add `expand_referenced_types(callable_api, index, *, budget)` to
  `scripts/solidity_index.py`. **Type detection (L2, robust):** iterate the struct/enum
  **names the index already knows** and expand those whose name appears in the `callable_api`
  text (membership test — no signature-string parsing); emit their definitions via the
  existing `_render_struct`/`_render_enum`; expand one level of nested struct/enum fields;
  dedup by name; budget-bound. Inject the output into the draft grounding in
  `scripts/poc_queue_runner.py` (`_grounding`/callable-api assembly). Lookup response
  unchanged (FR-005).

**Checkpoint**: the model sees real struct fields before it constructs the type.

---

## Phase 4: User Story 3 — Lesson capture fires only on real progress (Priority: P2)

**Goal**: the spec-014 loop captures a candidate only on a genuinely-better verdict, never
on a lateral/regression error change.

**Independent Test**: quickstart.md #3.

### Tests for User Story 3 (write first, expect red)

- [X] T008 [P] [US3] `tests/unit/test_capture_trigger.py`: drive `_maybe_capture_lesson`
  with — stuck→compiled (or real_pass) ⇒ exactly one candidate; stuck→different error, not
  compiled ⇒ zero; stuck→vacuous_pass ⇒ zero; and a resolved-then-recurring signature ⇒
  dedup still holds one (FR-006/FR-007; SC-004/SC-005).

### Implementation for User Story 3

- [X] T009 [US3] Tighten `_maybe_capture_lesson` in `scripts/poc_queue_runner.py`: accept the
  current `compiled`/`real_pass` flags and require a genuinely-better verdict (compiled or
  real_pass, prior non-empty signature cleared) — drop the "prev signature absent ⇒ resolved"
  sole trigger; never capture on a lateral/regression change or vacuous pass. Update the call
  site in `_process_finding` to pass `compiled`/`real_pass`. Dedup + gate unchanged (FR-007).

**Checkpoint**: a regression no longer manufactures a false-positive lesson.

---

## Phase 5: Polish & Cross-Cutting

- [X] T010 Run the full offline suite (`tests/unit tests/integration tests/architecture
  tests/security tests/frontend`); confirm all green with the new tests, no new dependency,
  and no change to any kernel-invariant test (FR-009/SC-006).
- [X] T011 Update `docs/roadmap.md`: spec 015 landed (harness robustness from the first live
  H-01 run), and record the gotchas the run surfaced — native tool-calling → empty PoCs on
  this model (use marker); prose-wrapped output → clean-Solidity extraction; false lesson
  capture on regression → compile-gated trigger; struct-field timing → proactive grounding.

---

## Dependencies & Execution Order

- **Setup (T001)** → **US1 (T002–T005)** / **US2 (T006–T007)** / **US3 (T008–T009)**, which
  are mutually independent (distinct code paths); within each, tests precede implementation.
- **Polish (T010–T011)** last (needs all three).

### Parallel opportunities

- T002/T003/T004 (US1 tests), T006 (US2 test), T008 (US3 test) are all `[P]` (distinct
  files). The three implementation tracks (T005, T007, T009) can proceed in parallel once
  their tests are red.

---

## Implementation Strategy

### MVP (Setup + US1)
Clean-Solidity extraction is the highest-leverage fix — it turns wasted/vacuous attempts into
real ones and stops the prose-in-`.sol` corruption. Ship first.

### Then grounding + loop hygiene (US2, US3)
US2 removes the struct-field guessing; US3 stops the loop capturing junk. Both additive and
independently testable.

### Notes
- Behavior-preserving on the happy path (a clean fenced reply extracts identically).
- No kernel invariant, DATA-wrap, trust hierarchy, or promotion gate changes (FR-009).
- Commit per logical group on explicit request (project convention).
