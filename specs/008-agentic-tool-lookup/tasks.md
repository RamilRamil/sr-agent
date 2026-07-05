# Tasks: Native Agentic Tool-Calling for PoC Symbol Lookup

**Input**: Design documents from `/specs/008-agentic-tool-lookup/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R6), data-model.md,
contracts/{tool-calling-protocol,protocol-selection}.md, quickstart.md

**Tests**: INCLUDED — this feature's own completion bar (SC-001–004) is explicitly
"verified entirely offline," and the project's constitution requires test-first for
security-adjacent behavior; every offline scenario in quickstart.md maps to a task
below. No model/GPU/Docker needed for any task except the optional US4 live check.

**Organization**: By user story, in priority order — US1 (P1, MVP: the structured
round-trip itself) → US2 (P1, byte-identical resolution/logging contract across
protocols) → US3 (P2, graceful fallback + explicit override) → US4 (P3, optional
live comparison). All stories share one Foundational phase (capability detection +
chat transport), since every story needs both.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files, no dependency on an incomplete task
- **[Story]**: US1…US4 (Setup/Foundational/Polish carry no story label)

---

## Phase 1: Setup

- [X] T001 Confirm the foundation research.md R2 assumes is real: `GET /api/tags`
  on the project's local `ollama` Docker container (or the Kaggle tunnel) returns
  a `capabilities` list per model entry including `"tools"` for
  `qwen2.5-coder:7b`/`qwen3-coder:30b` — no code change, a sanity checkpoint before
  building `supports_tools()` against it.

**Checkpoint**: the capability signal this whole feature depends on is confirmed
present in the actual API response shape, not just documented.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: blocks all user stories — every story needs both capability
detection and the chat transport.

- [X] T002 [P] Implement `LocalClient.supports_tools() -> bool` in
  `sr_agent/llm_core/local_client.py` (research.md R2) — reuse `available()`'s
  existing model-tag-matching logic against `/api/tags`, checking `"tools"` in the
  matched entry's `capabilities` list.
- [X] T003 [P] Implement `LocalClient.chat(messages, tools=None, options=None) ->
  dict` in `sr_agent/llm_core/local_client.py` (research.md R3/R5) — `POST
  /api/chat`, same streaming-safety discipline as `generate()` (roadmap gotcha
  #11/#12: `stream: true`, reassemble NDJSON, raise `ModelUnavailableError` if
  `done: true` is never seen), returning the parsed final message (`content` +
  `tool_calls`).
- [X] T004 Add a `--lookup-protocol {auto,tool,marker}` CLI flag (default `auto`)
  to `scripts/poc_queue_runner.py`'s `main()`, and implement `_select_protocol()`
  per contracts/protocol-selection.md's decision table — not yet wired to any
  round-trip logic (depends on T002).

**Checkpoint**: capability detection and chat transport exist and are
independently callable; `_select_protocol()` returns the right mode for every row
of the decision table. No round-trip logic yet.

---

## Phase 3: User Story 1 — A structured tool call resolves a real symbol (Priority: P1) 🎯 MVP

**Goal**: The model's lookup request is a genuine, schema-declared tool call the
inference API parses and returns as a typed object — not a text pattern the
harness hopes to find.

**Independent Test**: quickstart.md #2 — a scripted `chat()` response containing
`message.tool_calls` for `lookup_symbol` resolves via the real `SymbolIndex`
(spec 007's fixture), with no text-pattern regex involved in detection.

### Tests for User Story 1

- [X] T005 [P] [US1] `tests/unit/test_local_client.py::test_chat_detects_tool_calls`
  — a scripted NDJSON response containing a `tool_calls` field on the final
  message is parsed into `{"content": ..., "tool_calls": [...]}`.
- [X] T006 [P] [US1] `tests/unit/test_local_client.py::test_supports_tools_true_false`
  — a model whose `/api/tags` entry lists `"tools"` reports `True`; one that
  doesn't reports `False` (quickstart.md #1).

### Implementation for User Story 1

- [X] T007 [US1] Define the `lookup_symbol` tool JSON schema (contracts/
  tool-calling-protocol.md) as a module-level constant in
  `scripts/poc_queue_runner.py`.
- [X] T008 [US1] Implement `_generate_with_tool_calls()` in
  `scripts/poc_queue_runner.py`, parallel to spec 007's
  `_generate_with_lookups()`: call `LocalClient.chat()` with the tool schema,
  detect `tool_calls`, resolve each via `SymbolIndex.lookup()` (up to the
  remaining lookup budget), append the assistant message + one `{"role":
  "tool", ...}` message per call, re-issue `chat()`, and once no `tool_calls`
  remain (or budget is exhausted) return the final content stripped of markdown
  fences (FR-007) (depends on T003, T007).
- [X] T009 [US1] Wire `_generate_with_tool_calls()` into `draft()`/`fix()` in
  `scripts/poc_queue_runner.py`, selected when `_select_protocol()` returns
  `tool` (depends on T004, T008).

**Checkpoint**: a scripted fake tool-calling round-trip resolves a real struct
lookup end-to-end and is observable in the run log — no live model needed
(mirrors spec 007's own US1 checkpoint).

---

## Phase 4: User Story 2 — Byte-identical resolution/logging across both protocols (Priority: P1)

**Goal**: This feature changes ONLY the transport — never what a lookup returns,
how ambiguity is handled, or how it's logged.

**Independent Test**: quickstart.md's SC-002 case — the same symbol set
(qualified-name fallback, nested-type struct/enum, ambiguous multi-match,
not-found) resolved through both protocols produces byte-identical rendered
content and identical `{"event": "lookup", ...}` log shape.

### Tests for User Story 2

- [X] T010 [P] [US2]
  `tests/unit/test_poc_queue_runner.py::test_tool_and_marker_protocols_resolve_identically`
  — run the same fixture symbols (from `tests/unit/test_solidity_index.py`'s
  fixture: `TBalanceState`, qualified `ICooldown.TBalanceState`, `cancel`'s
  ambiguous match, a not-found name) through both `_generate_with_lookups()` and
  `_generate_with_tool_calls()`; assert identical rendered text and identical
  logged `(symbol, resolved, match_count)` tuples.

### Implementation for User Story 2

- [X] T011 [US2] Extract the per-symbol rendering logic already in spec 007's
  `_render_lookup_response()` (including the nested-type-import NOTE) into a
  shared helper both `_generate_with_lookups()` and `_generate_with_tool_calls()`
  call — so byte-identical output is structural (one implementation), not
  maintained by keeping two renderers in sync by hand (depends on T008).

**Checkpoint**: SC-002 holds by construction — a future change to rendering logic
cannot silently diverge between protocols, since there is only one
implementation of "how a lookup result is rendered."

---

## Phase 5: User Story 3 — Automatic, correct fallback for non-tool-capable models (Priority: P2)

**Goal**: The harness keeps working, unmodified, against any model/host without
tool-calling support — and an operator can explicitly force either protocol.

**Independent Test**: quickstart.md #4/#5 — a scripted non-tool-capable
`/api/tags` response falls back to spec 007's `LOOKUP:` path automatically;
`--lookup-protocol tool` on such a model errors clearly at startup;
`--lookup-protocol marker` forces the text-marker path even on a tool-capable
model.

### Tests for User Story 3

- [X] T012 [P] [US3]
  `tests/unit/test_poc_queue_runner.py::test_auto_selects_marker_when_not_tool_capable`
- [X] T013 [P] [US3]
  `tests/unit/test_poc_queue_runner.py::test_forced_tool_protocol_errors_on_incapable_model`
- [X] T014 [P] [US3]
  `tests/unit/test_poc_queue_runner.py::test_forced_marker_protocol_on_capable_model`

### Implementation for User Story 3

- [X] T015 [US3] Complete `_select_protocol()`'s decision table in
  `scripts/poc_queue_runner.py` (protocol-selection.md), including the startup
  error path for `--lookup-protocol tool` on an incapable model (depends on
  T004; T012–T014 should fail before this task and pass after).
- [X] T016 [US3] Log `{"event": "lookup_protocol", "mode": ..., "source": ...}`
  once per run in `main()`, alongside the existing `scaffold_mode` log entry
  (depends on T015).

**Checkpoint**: the harness works end-to-end, unmodified, against a
non-tool-capable model (spec 007's existing behavior fully preserved), and an
operator can force either protocol explicitly for debugging/comparison.

---

## Phase 6: User Story 4 — Optional live comparison against spec 007's H-01 baseline (Priority: P3)

**Goal**: An honest, optional answer to "does native tool-calling change anything
observable on the real finding spec 007 already tested" — NOT a requirement.

**Independent Test**: quickstart.md #6.

- [X] T017 [US4] (OPTIONAL — not required for feature completion, FR-009) Run
  `scripts/poc_queue_runner.py --only H-01 --fork --lookup-protocol auto` against
  a fresh Kaggle tunnel + `qwen3-coder:30b`. Depends on Phase 3/4/5 (US1–US3)
  being complete.
- [X] T018 [US4] (OPTIONAL, only if T017 is run) Record the honest comparison
  against spec 007's already-documented H-01 baseline in `docs/roadmap.md` —
  "no observable difference" is an acceptable, valid outcome (this feature
  changes transport, not resolution logic).

**Checkpoint**: if pursued, a documented before/after exists; if not pursued, the
feature is still complete per FR-009's explicit stance.

---

## Phase 7: Polish & Cross-Cutting

- [X] T019 [P] Run the full existing suite (`tests/unit tests/architecture
  tests/security tests/frontend`, 247 passing as of spec 007/T020) and confirm
  zero regressions — this feature must not touch `SymbolIndex` resolution,
  kernel behavior, or spec 007's existing text-marker path.
- [X] T020 Update `docs/roadmap.md` noting spec 008's completion: offline
  validation results (SC-001–004), and the live-comparison status (T017/T018 —
  run or explicitly deferred).

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002-T004, blocks all stories)** → user
  stories.
- **US1 (T005-T009)** is the MVP — the tool-calling round-trip working
  end-to-end for a real symbol. Do it first.
- **US2 (T010-T011)** depends on US1's round-trip code (T008) already existing;
  it unifies rendering so both protocols share one implementation.
- **US3 (T012-T016)** depends on Foundational (T004); benefits from US1 existing
  (to have something to fall back FROM) but its own tests can be written against
  `_select_protocol()` alone.
- **US4 (T017-T018)** depends on US1-US3 all being complete; optional, per FR-009.
- **Polish (T019-T020)**: after everything.

### Parallel opportunities

- Foundational: T002/T003 in parallel (different concerns in the same file, no
  shared state); T004 after both.
- Within US1: T005/T006 (tests) in parallel; T007 before T008 (schema needed
  first); T009 after T008.
- Within US2: T010 alone (single test task).
- Within US3: T012/T013/T014 in parallel (independent test scenarios).
- US2's work (T010-T011) can proceed in parallel with US3's (T012-T016) — both
  only depend on US1 (T008) / Foundational (T004) respectively, not on each
  other.

---

## Implementation Strategy

### MVP (Setup + Foundational + US1)

The tool-calling round-trip resolves a real symbol end-to-end and is observable
in the run log, entirely offline. STOP and validate (T005/T006) before touching
a live model.

### Then close the correctness contract (US2) and harden (US3)

US2 proves — by construction, not by parallel maintenance — that switching
transport didn't change what gets resolved or logged. US3 proves the harness
still works, unmodified, for every model that doesn't support tool-calling, and
gives the operator an explicit override.

### Then, optionally, validate live (US4)

Only if the operator explicitly wants to spend the Kaggle GPU budget on it — a
"no observable difference" result is a complete, valid deliverable per this
feature's own spec.

### Notes

- No new dependency — Ollama's `/api/chat` is reached via the same stdlib
  `urllib` pattern `LocalClient` already uses (T002/T003).
- Spec 007's `SymbolIndex`, its resolution semantics, and its `LOOKUP:`
  text-marker path are NOT modified except where US3 wires in automatic
  selection — the existing path itself stays byte-for-byte as spec 007 left it.
- Every test task uses the SAME real-target fixtures spec 007's own tests
  already established (`tests/unit/test_solidity_index.py`'s fixture project),
  not new synthetic data, so US2's byte-identical comparison is meaningful.
- Commit per task or logical group (on explicit request per project convention).
