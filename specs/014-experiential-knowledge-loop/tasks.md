# Tasks: Experiential Knowledge Loop (v1)

**Input**: Design documents from `/specs/014-experiential-knowledge-loop/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R6), data-model.md, contracts/
(lesson-lifecycle, lessons-cli), quickstart.md

**Tests**: INCLUDED and test-first — the constitution mandates security-critical
guarantees (human-gate, tamper-evidence, DATA-wrap, no-self-promotion) be written as a
failing test before the implementation. Every SC maps to a task. All offline (FR-010).

**Organization**: By user story — US1 (P1, human-gated promotion) → US2 (P2, retrieve as
suggestion) → US3 (P2, capture + dedup). US1/US2/US3 are independent after the
Foundational phase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files / independent, may run in parallel
- **[Story]**: US1…US3 (Setup/Foundational/Polish carry no story label)

---

## Phase 1: Setup

- [X] T001 Confirm the reusable primitives exist and are importable (no code): `sr_agent/
  memory/hmac.py` (`sign`/`verify`), `sr_agent/memory/knowledge.py` (`KnowledgeBase.search`,
  lexical fallback), the confirmation-store pattern in `sr_agent/orchestrator/
  confirmation.py`, `config.secret_key`/`config.memory_root`, and the harness's
  `_error_signature`/`_fail_signature` + `prev_error_sig`/`prev_fail_sig` in
  `scripts/poc_queue_runner.py`. Re-confirm no new dependency is needed (FR-008).

**Checkpoint**: the wiring targets are confirmed present.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the shared kernel module all three stories build on. No story-specific logic.

- [X] T002 Create `sr_agent/memory/lessons.py` with the data models and the `sig_id`
  helper (data-model.md): `LessonCandidate` {sig_id, trigger_signature, symptom, fix
  (mechanical diff/snippet — no model call, U1), provenance{origin="llm_inference",
  finding_id, attempt, captured_at}, category, status}; `PromotedLesson`
  {sig_id, category, content, content_hash, hmac, promoted_at (tz-aware, spec-013
  convention), origin="llm_inference" (immutable audit), authorization="human_input"
  (set on promote, Principle IV)}; `sig_id(trigger_signature) = sha256(canonical(sorted(sig)))[:16]`.
- [X] T003 Add the `LessonStore` skeleton in `sr_agent/memory/lessons.py`: constructor
  `(lessons_root, knowledge_root, secret_key, embedder=None)`, path helpers for
  `lessons/pending/<sig_id>.json`, `knowledge/lessons/<sig_id>.md`, and
  `knowledge/lessons/_manifest.jsonl`; private `_sign(fields)`/`_verify(fields,hmac)`
  delegating to `hmac_module` with `secret_key` (reuse, do not reimplement).
- [X] T004 Wire config: a `lessons_root` on the config/CLI context (default alongside
  `confirmations_root`/`memory_root`), and a `knowledge/lessons/` corpus path — so the CLI
  and harness construct a `LessonStore` the same way `confirm` constructs its dirs.
  **W1**: confirm the harness (`scripts/poc_queue_runner.py`) can obtain `config.secret_key`
  offline for retrieval-time HMAC verification (same construction the CLI uses); capture
  needs no key (candidates are unsigned). If the key is unavailable at retrieval, lessons
  fail verification and are dropped (fails safe, but US2 goes silent) — so this wiring is
  load-bearing for US2 and must be verified, not assumed.

**Checkpoint**: the module + models + store scaffolding import cleanly; all three stories
can start in parallel.

---

## Phase 3: User Story 1 — Human-gated promotion of a lesson (Priority: P1) 🎯 MVP

**Goal**: a candidate becomes retrievable knowledge only via out-of-band human approval,
and every promoted lesson is tamper-evident.

**Independent Test**: quickstart.md #1 — seed a pending candidate by hand, drive
`sr-agent lessons list/show/approve/dismiss`, verify signature + tamper detection.

### Tests for User Story 1 (write first, expect red)

- [X] T005 [P] [US1] `tests/unit/test_lessons_store.py`: `promote()` writes
  `knowledge/lessons/<sig_id>.md` + a signed manifest record whose HMAC verifies; a
  hand-edit of the `.md` (content_hash/HMAC mismatch) makes `verify()` report INVALID and
  `retrieve()` drop it silently; `dismiss()` deletes the pending file and never writes to
  the corpus; `promote()` sets `authorization == "human_input"` (Principle IV) **and**
  preserves the immutable `origin == "llm_inference"` (never rewrites origin — the two
  facts stay distinct, per C1's reconciliation).
- [X] T006 [P] [US1] `tests/architecture/test_lessons_promote_gate.py`: AST-scan
  `scripts/poc_queue_runner.py` and the orchestrator modules; assert none reference/call
  `LessonStore.promote` (or the module-level promote symbol) — promotion is out-of-band
  only (SC-004), mirroring spec 013's `test_harness_sandbox_only.py` style, with a negative
  check proving the guard would catch an injected `store.promote(...)` call.

### Implementation for User Story 1

- [X] T007 [US1] Implement `list_pending()`, `show(sig_id)`, `dismiss(sig_id)`,
  `promote(sig_id, edited=None)`, and `verify()` in `sr_agent/memory/lessons.py` per
  contracts/lesson-lifecycle.md — `promote` is the sole writer of the promoted store,
  signs via `_sign`, records `content_hash`, removes the pending file.
- [X] T008 [US1] Add the `sr-agent lessons` click command to `sr_agent/cli.py`
  (list/show/approve/dismiss/verify **and `add`**) per contracts/lessons-cli.md, mirroring
  `confirm_cmd` — the `approve` subcommand is the ONLY caller of `LessonStore.promote`;
  `verify` exits non-zero on any invalid lesson (like `memory verify`). **G1**: `add
  --from <file>` lets the operator introduce a hand-authored candidate into the pending
  queue (the seeding affordance — a candidate that didn't come from capture, e.g. the 13
  gotchas), which is then reviewed/approved through the same gate. Without it there is no
  way to onboard non-captured lessons through the human path.

**Checkpoint**: US1 is independently demoable — the gate works, tamper is detected, and no
agent path can promote.

---

## Phase 4: User Story 2 — Retrieve a promoted lesson as a suggestion (Priority: P2)

**Goal**: promoted lessons relevant to the current draft/fix context surface DATA-wrapped,
as reference only; inert when the corpus is empty; no new dependency.

**Independent Test**: quickstart.md #2 — with one promoted lesson, assert a DATA-wrapped
block appears in the draft/fix prompt; empty corpus → byte-identical prompt.

### Tests for User Story 2 (write first, expect red)

- [X] T009 [P] [US2] `tests/integration/test_lessons_retrieve.py`: with a promoted lesson
  matching the context, `retrieve()` returns `[DATA START]…[DATA END]`-wrapped strings and
  the harness draft/fix prompt includes the block; with an empty/irrelevant corpus,
  `retrieve()` returns `[]` and the assembled prompt is **byte-identical** to pre-feature
  (SC-007); works with `embedder=None` (lexical fallback, SC-006).
- [X] T010 [P] [US2] `tests/security/test_lesson_not_instruction.py`: a promoted lesson
  whose text contains instruction-like content ("ignore prior steps and…") is surfaced
  wrapped as DATA and cannot alter harness control flow — the DATA-wrap invariant holds
  (SC-005), in the style of the existing `tests/security/` MI assertions.

### Implementation for User Story 2

- [X] T011 [US2] Implement `LessonStore.retrieve(context, top_k)` in
  `sr_agent/memory/lessons.py`: category-scoped `KnowledgeBase.search` over
  `knowledge/lessons/`, verify each hit's manifest HMAC+content_hash and drop unverified
  silently, return DATA-wrapped strings (or `[]`).
- [X] T012 [US2] Add the retrieval hook to `draft()`/`fix()` prompt assembly in
  `scripts/poc_queue_runner.py`: build a `LessonStore`, call `retrieve` with the finding
  context (draft) / current error text (fix), append the DATA-wrapped block only when
  non-empty (inert otherwise). Guard so a retrieval error never breaks drafting.

**Checkpoint**: US2 works with a manually promoted lesson; prompt unchanged when unused.

---

## Phase 5: User Story 3 — Automatic capture, deduplicated (Priority: P2)

**Goal**: the harness proposes exactly one candidate per distinct resolved error-signature,
best-effort and non-blocking.

**Independent Test**: quickstart.md #3 — drive `_process_finding` (offline fake
model/sandbox) through a stuck→resolved signature; assert one candidate; a repeat adds zero.

### Tests for User Story 3 (write first, expect red)

- [X] T013 [P] [US3] `tests/integration/test_lessons_capture.py` (reuse the spec-009
  fake-model + fake-sandbox harness): a run where attempt N is stuck on an error-signature
  and N+1 resolves it emits exactly **one** candidate with the correct fields
  (trigger/symptom/fix/provenance.origin="llm_inference"/category); a second identical
  resolved-signature transition adds **zero** further candidates (dedup by `sig_id`,
  SC-001); a forced `capture` write failure does NOT abort the run (FR-001).

### Implementation for User Story 3

- [X] T014 [US3] Implement `LessonStore.capture(candidate)` in `sr_agent/memory/lessons.py`:
  write `lessons/pending/<sig_id>.json` iff no pending file and no promoted manifest record
  for that `sig_id` (dedup, FR-002); best-effort — swallow+log any error, never raise
  (FR-001).
- [X] T015 [US3] Add the capture hook in `_process_finding` (`scripts/poc_queue_runner.py`):
  at the resolved-error-signature transition (`prev_error_sig`/`prev_fail_sig` was non-empty
  and now cleared), build a `LessonCandidate` and call `store.capture(...)` inside a
  best-effort guard; skip if already pending/promoted.

**Checkpoint**: capture fills the queue automatically and quietly; dedup holds.

---

## Phase 6: Polish & Cross-Cutting

- [X] T016 Seed content: onboard the 13 confirmed gotchas from `docs/roadmap.md` through
  the gate — `sr-agent lessons add --from <file>` to queue each as a candidate (G1), then
  `lessons approve` (optionally `--edit`), landing signed entries under `knowledge/lessons/`.
  Content step through the human path — never written straight to the corpus by automation.
- [X] T017 Run the full offline suite (`tests/unit tests/integration tests/architecture
  tests/security tests/frontend`); confirm all green, no new dependency, no new `utcnow`
  warnings, and the harness prompt is byte-identical when the corpus is empty (SC-006/SC-007).
- [X] T018 Update `docs/roadmap.md`: Phase 6 v1 landed (experiential knowledge loop —
  capture/queue/gate/promote/retrieve, one producer = harness, retrieve into draft/fix,
  dedup by error-signature); note the deferred v2 (audit-loop producer, free-form lessons).

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T004)** → all user stories.
- **US1 (T005–T008)**, **US2 (T009–T012)**, **US3 (T013–T015)** are independent after
  Foundational; within each, tests (write-first, red) precede implementation.
- US2's demo needs a promoted lesson — use US1's `promote` or a signed fixture; the code is
  independent.
- **Polish (T016–T018)** last (T016 needs the US1 gate; T017 needs all stories).

### Parallel opportunities

- After Foundational: T005/T006 (US1 tests), T009/T010 (US2 tests), T013 (US3 test) are all
  `[P]` (distinct files). The three implementation tracks can proceed in parallel once their
  tests are red.

---

## Implementation Strategy

### MVP (Setup + Foundational + US1)
The human-gated, tamper-evident promotion path — the security spine. Even fed by hand it
delivers a curated, verifiable knowledge corpus grown under operator authority. Ship first.

### Then the payoff and the automation (US2, US3)
US2 turns promoted lessons into saved metered-run time (retrieve as suggestion); US3 makes
the loop "capture-always". Both are additive and independently testable.

### Notes
- Reuse-first: `hmac.py`, `KnowledgeBase`, the confirmation pattern, the harness signatures
  — this feature is wiring, not new primitives.
- Security-critical guarantees are test-first (T005/T006/T010). No feature changes the trust
  hierarchy or the DATA-wrap rule; both are relied upon.
- Commit per logical group on explicit request (project convention).
