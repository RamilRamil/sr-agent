# Tasks: AST-Grounded, Agentic Lookup for PoC Drafting

**Input**: Design documents from `/specs/007-ast-grounded-poc-drafting/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R8), data-model.md, contracts/{lookup-protocol,symbol-index-query}.md, quickstart.md

**Tests**: INCLUDED — the spec's own User Stories 1 and 3 are explicitly about
verifiable correctness (struct-field resolution, the dedup-collision bug class), and
`quickstart.md` already specifies the exact offline test cases against real target
fixtures. No model/GPU needed for any test task; only the live-validation task (US4)
needs one.

**Organization**: By user story, in priority order — US1/US2 (P1) → US3 (P2,
correctness of the parsing foundation) → US4 (P2, live validation). All of US1-US3
share one Foundational phase (the `SymbolIndex` itself), since every story queries it.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files, no dependency on an incomplete task
- **[Story]**: US1…US4 (Setup/Foundational/Polish carry no story label)

---

## Phase 1: Setup

- [X] T001 Add `solidity-parser` as a documented harness dependency (e.g.
  `scripts/requirements.txt`, or a docstring-documented `pip install` step in
  `scripts/poc_queue_runner.py`) — per research.md R5, NOT `sr_agent`'s core
  `pyproject.toml`. Verify `.venv/bin/pip install solidity-parser` succeeds and pulls
  in only `antlr4-python3-runtime`.

**Checkpoint**: dependency installs cleanly; no change to `sr_agent`'s own dependency surface.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: blocks all user stories — every story queries `SymbolIndex`.

- [X] T002 Create `scripts/solidity_index.py` with the `Symbol` dataclass (name, kind,
  contract, file, definition, modifiers) per data-model.md.
- [X] T003 Implement `SymbolIndex.build(project_root: Path)` in
  `scripts/solidity_index.py` — parse every `.sol` file via `solidity_parser.parser`,
  catching and recording per-file parse failures in `unparsed_files` rather than
  raising (research.md R8; contracts/symbol-index-query.md's failure-modes table).
- [X] T004 Implement `SymbolIndex.lookup(name: str) -> list[Symbol]` in
  `scripts/solidity_index.py` — exact-name match across all parsed files, returning
  EVERY match (never guesses a single one under ambiguity — research.md R3).
- [X] T005 [P] Implement per-kind `Symbol.definition` rendering in
  `scripts/solidity_index.py`: struct → every field+type; function → full signature +
  every real modifier invocation; enum → every value; state variable → declared
  type+visibility (contracts/symbol-index-query.md).

**Checkpoint**: `SymbolIndex.build(<target>).lookup("TBalanceState")` returns the real
5-field struct offline, no model needed.

---

## Phase 3: User Story 1 — Model stops inventing struct fields (Priority: P1) 🎯 MVP

**Goal**: The model can request and receive a struct's real fields instead of
inventing plausible-sounding ones.

**Independent Test**: quickstart.md #1 — `lookup("TBalanceState")` matches the real
source; a nonexistent symbol resolves to `[]`, never fabricated.

### Tests for User Story 1

- [X] T006 [P] [US1] `tests/unit/test_solidity_index.py::test_struct_fields_real` —
  `SymbolIndex.build(<real target fixture>).lookup("TBalanceState")` returns the real
  fields (`pending, claimable, nextUnlockAt, nextUnlockAmount, totalRequests`) and
  does NOT contain an invented `shares` field (quickstart.md #1).
- [X] T007 [P] [US1] `tests/unit/test_solidity_index.py::test_not_found_never_fabricated`
  — `lookup("TotallyMadeUpStructName")` returns `[]` (FR-008/SC-005).

### Implementation for User Story 1

- [X] T008 [US1] Implement lookup-request detection in `scripts/poc_queue_runner.py`
  (a `LOOKUP: <name>` line-matching function) per
  contracts/lookup-protocol.md — depends on T004.
- [X] T009 [US1] Wire the bounded lookup round-trip into `draft()`/`fix()` in
  `scripts/poc_queue_runner.py`: on detecting one or more `LOOKUP:` lines (up to the
  remaining budget), resolve each via `SymbolIndex.lookup()`, render the `[DATA]`
  response per contracts/lookup-protocol.md, re-prompt, and only accept the model's
  output as final once no `LOOKUP:` lines remain OR the budget is exhausted (depends
  on T008).
- [X] T010 [US1] Add `--lookup-budget` CLI flag (default 3) to
  `scripts/poc_queue_runner.py`'s `main()`, and log every lookup as its own
  `{"event": "lookup", "finding_id", "attempt", "symbol", "resolved", "match_count"}`
  entry (FR-004/SC-004; data-model.md's Lookup Request/Lookup Budget).

**Checkpoint**: a draft/fix turn that emits `LOOKUP: TCancelGuard` gets back the real
field list and can be observed in the run log — testable without a live model via a
scripted fake provider, exactly like this session's earlier `mechanism_signal`
validations.

---

## Phase 4: User Story 2 — Generalizes to any symbol kind (Priority: P1)

**Goal**: The SAME lookup mechanism resolves structs, enums, functions, and
modifiers — no per-kind special-casing in the protocol/round-trip code.

**Independent Test**: quickstart.md-style checks for a function and an enum, using
the identical `lookup()`/round-trip code path already built in US1.

### Tests for User Story 2

- [X] T011 [P] [US2] `tests/unit/test_solidity_index.py::test_function_signature_and_modifiers`
  — `lookup("cancel")` resolves with its full signature AND its real
  `onlyUser(user)` modifier captured in `Symbol.modifiers`.
- [X] T012 [P] [US2] `tests/unit/test_solidity_index.py::test_enum_values` — lookup of
  a real enum in the target project resolves with every declared value.

### Implementation for User Story 2

- [X] T013 [US2] No new protocol/round-trip code should be required for T011/T012 to
  pass — if any IS required, that is itself a signal the round-trip built in US1 was
  accidentally kind-specific; fix `scripts/poc_queue_runner.py`'s lookup handling to
  be kind-agnostic (depends on T008-T010 from US1, T005 from Foundational).

**Checkpoint**: adding support for a symbol kind not seen yet in a future finding
requires only a `SymbolIndex` parsing change, never a new prompt-protocol special case
(spec's own US2 Acceptance Scenario 2).

---

## Phase 5: User Story 3 — Grammar-correct parsing (Priority: P2)

**Goal**: The dedup-collision bug class (two symbols sharing identical rendered text,
one silently dropped) cannot recur, because resolution never depends on
rendered-text deduplication.

**Independent Test**: quickstart.md #2 — two functions sharing an identical modifier
set are BOTH retrievable by name.

### Tests for User Story 3

- [X] T014 [P] [US3] `tests/unit/test_solidity_index.py::test_shared_modifier_no_collision`
  — two real functions in the target project sharing the exact same modifier(s) each
  resolve correctly and independently via `lookup()` on their own names (SC-002; the
  exact bug class from this session's regex-based `callable_api` annotation collision).
- [X] T015 [P] [US3] `tests/unit/test_solidity_index.py::test_unparseable_file_degrades_gracefully`
  — a directory containing one malformed/unsupported `.sol` file still builds a
  usable index for the OTHER files; the bad file appears in `unparsed_files`, build()
  does not raise (FR-009/research.md R8).

### Implementation for User Story 3

- [X] T016 [US3] If T014/T015 reveal any gap in T003's per-file error handling or T004's
  per-name lookup (e.g. an index keyed in a way that only stores one Symbol per name),
  fix `scripts/solidity_index.py` so lookups are always name→list, never name→single
  (depends on T003, T004).

**Checkpoint**: the specific failure class from spec 006/this session (rendered-text
dedup silently dropping one of two identical-looking entries) is structurally
impossible in `SymbolIndex`, not just patched for one observed instance.

---

## Phase 6: User Story 4 — Evidence from the hardest known case (Priority: P2)

**Goal**: An honest, recorded answer to "did this change anything for H-01" — not a
requirement that H-01 now passes.

**Independent Test**: quickstart.md #4 — a live run against H-01 with the lookup
mechanism enabled, with lookups visible in the run log.

- [X] T017 [US4] Run `scripts/poc_queue_runner.py --only H-01 --fork --lookup-budget 3`
  (fresh Kaggle-hosted local model tunnel + `MAINNET_RPC_URL`, same setup as this
  session's other fork runs) per quickstart.md #4. Depends on Phase 3 (US1) being
  complete; Phase 4/5 improve robustness but are not blocking for this run to be
  attempted.
- [X] T018 [US4] Record the outcome in `docs/roadmap.md`'s PoC-workability section
  (FR-007/SC-003): whether/which lookups were issued and resolved, and how the
  attempt-by-attempt error signature compares to this session's already-logged
  pre-lookup H-01 runs — honestly, whether or not H-01 ultimately passes (per
  [[project_poc_vacuous_pass]] / spec 006's positive-signal, no-overclaiming
  discipline).

**Checkpoint**: a documented, honest before/after comparison exists for the hardest
known finding — the feature's actual deliverable per its own spec, regardless of
whether H-01 converges.

---

## Phase 7: Polish & Cross-Cutting

- [X] T019 [P] Confirm existing static grounding (file map, callable_api, scaffold,
  few-shot example) is unaffected — re-run this session's earlier offline validations
  for those blocks (FR-005; quickstart.md #5).
- [X] T020 (optional, explicitly secondary per research.md R6) Re-platform
  `build_file_manifest`/`build_callable_api` in `scripts/poc_queue_runner.py` on top of
  `SymbolIndex` instead of their current regex extraction — closes SC-002 for those
  blocks too, but MUST NOT block T001-T018 from shipping first.

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002-T005, blocks all stories)** → user stories.
- **US1 (T006-T010)** is the MVP — the lookup mechanism working end-to-end for the
  motivating struct-field case. Do it first.
- **US2 (T011-T013)** depends on US1's round-trip code (T008-T010) already existing;
  it mostly ADDS TESTS proving that code is kind-agnostic, per its own Independent Test.
- **US3 (T014-T016)** depends on Foundational (T003/T004); independent of US1/US2's
  prompt-protocol code, but shares the same `SymbolIndex`.
- **US4 (T017-T018)** depends on US1 being complete (needs a working lookup mechanism
  to validate); benefits from but does not strictly require US2/US3.
- **Polish (T019-T020)**: T019 after everything; T020 explicitly optional/deferred.

### Parallel opportunities

- Foundational: T005 can run alongside T002-T004 once `Symbol`'s shape (T002) is fixed.
- Within US1: T006/T007 (tests) in parallel; T008 before T009 (round-trip needs
  detection first); T010 after T009.
- Within US2: T011/T012 in parallel.
- Within US3: T014/T015 in parallel.
- US3's tests (T014/T015) can run in parallel with US2's work (T011-T013) — both only
  depend on Foundational, not on each other.

---

## Implementation Strategy

### MVP (Setup + Foundational + US1)
The lookup mechanism resolves the motivating struct-field case end-to-end and is
observable in the run log. STOP and validate offline (T006/T007) before touching a
live model.

### Then generalize + harden (US2 → US3)
US2 proves the SAME mechanism already covers other symbol kinds (ideally zero new
code, only new tests). US3 hardens the parsing foundation against the exact bug class
that motivated this feature, plus graceful degradation.

### Then validate honestly (US4)
Run against H-01 live, record the true outcome — a negative or partial result is a
valid, complete deliverable per the spec's own explicit stance.

### Notes
- No new dependency touches `sr_agent`'s own `pyproject.toml` — harness-only (T001).
- Existing static grounding blocks are NOT modified in this feature except optionally,
  last, and only if it doesn't block shipping the lookup mechanism (T020).
- Every test task uses real target-project fixtures (the actual `.sol` files already
  in this session's target), not synthetic Solidity — matching this session's own
  practice of validating against ground truth before trusting a mechanism.
- Commit per task or logical group (on explicit request per project convention).
