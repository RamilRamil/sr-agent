# Tasks: Harness Prompt Management

**Input**: Design documents from `/specs/012-harness-prompt-mgmt/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R5), data-model.md,
contracts/prompt-management.md, quickstart.md

**Tests**: INCLUDED — the completion bar (SC-001–006) is explicitly offline; the
identical-behavior guarantee (FR-002) and version-recording (FR-003) must be pinned.
Every scenario maps to a task.

**Organization**: By user story, priority order — US1 (P1, versioned fetch + identical
fallback) → US2 (P1, version→trace) → US3 (P2, seeding). US1/US2 share the Foundational
`get_prompt_versioned` + `_resolve_prompt` building blocks.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files / independent, no dependency on an incomplete task
- **[Story]**: US1…US3 (Setup/Foundational/Polish carry no story label)

---

## Phase 1: Setup

- [X] T001 Define the stable-name → fallback-constant registry `_HARNESS_PROMPTS`
  (`poc-extract`/`poc-draft`/`poc-fix`/`poc-exploit-checklist`/`poc-lookup-marker`/
  `poc-synth-scaffold` → the six existing constants) in `scripts/poc_queue_runner.py`
  (data-model.md).

**Checkpoint**: the name↔constant registry exists (used by both routing and seeding).

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ blocks US1 and US2** — both need the versioned accessor + the resolve helper.

- [X] T002 Add `Tracer.get_prompt_versioned(name, fallback) -> tuple[str, int | None]`
  to `sr_agent/eval/tracer.py` (contracts/prompt-management.md, R1) — additive; returns
  `(fallback, None)` when disabled/failed, `(prompt.prompt, version)` otherwise. Leave
  `get_prompt` and its callers unchanged (FR-004).
- [X] T003 Implement `_resolve_prompt(tracer, name, fallback, **fmt) -> (text, {name,
  version})` in `scripts/poc_queue_runner.py` (R2): fetch via `get_prompt_versioned`,
  `.format(**fmt)`, on `KeyError`/`IndexError` fall back to the constant with
  `version=None` (FR-007); return the text + provenance dict (depends on T002).

**Checkpoint**: the versioned accessor and the resolve helper exist and are callable.

---

## Phase 3: User Story 1 — Versioned fetch, identical when tracing off (Priority: P1) 🎯 MVP

**Goal**: every harness prompt is fetched via `_resolve_prompt`, and a tracing-off run's
prompts are byte-identical to today's.

**Independent Test**: quickstart.md #1/#2/#3.

### Tests for User Story 1

- [X] T004 [P] [US1] `tests/unit/test_local_client.py::test_get_prompt_versioned` —
  disabled tracer → `(fallback, None)`; fake Langfuse client with a versioned prompt →
  `(text, version)`; raising client → `(fallback, None)` (SC-004).
- [X] T005 [P] [US1] `tests/unit/test_poc_queue_runner.py::test_resolve_prompt` —
  tracing off → byte-exact constant + `version None`; fake versioned tracer → fetched
  text + version; a fetched template missing a placeholder → the constant (FR-007).

### Implementation for User Story 1

- [X] T006 [US1] Route all six harness prompts through `_resolve_prompt` in
  `scripts/poc_queue_runner.py`: `draft`/`fix` (`poc-draft`/`poc-fix` +
  `poc-exploit-checklist`), `_traced_round_trip` (`poc-lookup-marker`, marker mode),
  `extract_tasks` (`poc-extract` — add a `tracer=NOOP_TRACER` param), `synthesize_scaffold`
  (`poc-synth-scaffold` — add a `tracer=NOOP_TRACER` param); thread the real tracer from
  `main()`/`_process_finding` into the two that gained the param (depends on T003).
- [X] T007 [US1] `tests/integration/test_poc_runner_loop.py::test_loop_prompt_identical_when_tracing_off`
  — with a disabled tracer, a draft's assembled prompt text equals the pre-feature
  constant-based prompt (capture via a spy on the fake client's received prompt)
  (FR-002/SC-001; depends on T006).

**Checkpoint**: prompts are versionable; a normal (tracing-off) run is byte-for-byte
unchanged. MVP.

---

## Phase 4: User Story 2 — A run records which prompt version produced it (Priority: P1)

**Goal**: each draft/fix generation's trace metadata records the prompt name(s)+version(s).

**Independent Test**: quickstart.md #4.

### Implementation for User Story 2

- [X] T008 [US2] Collect the `_resolve_prompt` provenance dicts in `draft`/`fix` and
  `_traced_round_trip` and pass them into the existing `tracer.generation(..., metadata=
  {..., "prompt_provenance": [...]})` call (contracts/prompt-management.md; depends on T006).

### Tests for User Story 2

- [X] T009 [P] [US2] `tests/integration/test_poc_runner_loop.py::test_generation_records_prompt_version`
  — with a fake tracer whose `get_prompt_versioned` returns a version and whose
  `generation` captures metadata, a draft/fix records `prompt_provenance` with the prompt
  name+version; a fallback-sourced prompt records `version: None` (SC-002/SC-003;
  depends on T008).

**Checkpoint**: a run is no longer prompt-version-blind — the trace says which version
produced which result.

---

## Phase 5: User Story 3 — Seed the harness prompts into Langfuse (Priority: P2)

**Goal**: the harness prompts exist in Langfuse (production, v1) to version against;
a clean no-op when disabled.

**Independent Test**: quickstart.md #5.

### Implementation for User Story 3

- [X] T010 [US3] Implement `seed_prompts(tracer)` in `scripts/poc_queue_runner.py`
  (contracts/prompt-management.md, R4): behind `tracer.enabled`, `create_prompt(name,
  prompt=constant, labels=["production"])` per `_HARNESS_PROMPTS`, each swallowing
  errors; a no-op when disabled. Invoke once at run start in `main()` (depends on T001).

### Tests for User Story 3

- [X] T011 [P] [US3] `tests/unit/test_poc_queue_runner.py::test_seed_prompts` — a
  disabled tracer → no-op (no error); a fake tracer with a fake Langfuse client → one
  `create_prompt` per harness prompt under `production` (SC-005; depends on T010).

**Checkpoint**: a versioned baseline exists to edit/roll-forward; disabled is a clean
no-op.

---

## Phase 6: Polish & Cross-Cutting

- [X] T012 Run the full offline suite
  (`tests/unit tests/integration tests/architecture tests/security tests/frontend`) and
  confirm all green with the new tests, offline, no Langfuse/Ollama/Docker/network, no
  target code embedded (SC-006/FR-008). Confirm the kernel suite is unaffected (SC-004).
- [X] T013 Update `docs/roadmap.md`: harness prompt management landed (roadmap item 4),
  leaving item 5 (datetime deprecations + more architecture invariants) as the last
  deferred harness-review candidate.

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002-T003)** → user stories.
- **US1 (T004-T007)**: T004/T005 after T002/T003; T006 before T007.
- **US2 (T008-T009)**: depends on T006 (routing) — provenance flows from the resolved
  prompts.
- **US3 (T010-T011)**: depends on T001 (registry); independent of US1/US2 wiring.
- **Polish (T012-T013)** last.

### Parallel opportunities

- Foundational: T002 then T003 (T003 depends on T002).
- US1: T004/T005 parallel; T006 before T007.
- US3 (T010-T011) can proceed in parallel with US1/US2 (only needs the registry T001).

---

## Implementation Strategy

### MVP (Setup + Foundational + US1)
Prompts are versionable AND a normal run is byte-identical (the fallback IS the
constant). Ship + validate the identical-behavior guarantee before anything else.

### Then the observability payoff (US2)
Record the prompt version in the trace — the reason to version at all.

### Then seed (US3)
Push the baseline so versioning can actually be used; a clean no-op without Langfuse.

### Notes
- No new dependency; Langfuse optional; all offline (FR-008).
- The only kernel-adjacent change is an ADDITIVE `Tracer` method (FR-004).
- This feature changes only WHERE prompts are fetched + that their version is recorded —
  never what a prompt SAYS (the constants are the v1 seed and the fallback).
- Commit per task or logical group (on explicit request per project convention).
