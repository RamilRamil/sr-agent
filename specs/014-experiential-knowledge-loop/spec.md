# Feature Specification: Experiential Knowledge Loop (v1)

**Feature Branch**: `014-experiential-knowledge-loop`

**Created**: 2026-07-10

**Status**: Draft

**Input**: User description: "Phase 6 — experiential knowledge loop (v1): close the
capture → queue → human-gate → promote → retrieve loop so the project stops
re-discovering the same reproducible lessons every metered run. Agent proposes; a human
promotes; only promoted, HMAC-signed lessons become retrievable (Principle IV). Mechanism
is kernel; content is pack. v1 wires exactly one producer (the PoC-workability harness),
retrieval into the draft/fix path only, dedup by error-signature, seeded by the 13
confirmed gotchas. All validation offline."

## User Scenarios & Testing *(mandatory)*

The "user" is the SR-agent **maintainer/operator**. The value: the project currently
re-discovers the same reproducible lessons (the 13 confirmed "gotchas" in
`docs/roadmap.md`) on every metered run because they live only in prose — nothing feeds
them back into the build-time knowledge the agent actually consults. This feature closes
that loop **under human authority**: the agent may only *propose* lessons; a human
*promotes* them; only promoted, tamper-evident lessons are ever retrieved, and only as a
*suggestion*, never as control.

### User Story 1 - Human-gated promotion of a lesson (Priority: P1) 🎯 MVP

As the operator, I need a lesson candidate to become retrievable knowledge **only after I
approve it**, and to be tamper-evident once promoted — because a lesson proposed by the
model is low-trust (`llm_inference`/`external_llm_output`, the bottom of the trust
hierarchy), and letting the agent grow its own retrievable knowledge would be a
memory-injection hole. Promotion must work exactly like `sr-agent confirm`: out-of-band,
in a separate process from the agent loop, so the agent can never promote its own
knowledge.

**Why this priority**: This is the security spine and the MVP. Without the human gate,
the whole loop is an unbounded self-poisoning channel; with it (even fed manually), the
operator already gets a curated, tamper-evident knowledge corpus grown under their
authority.

**Independent Test**: With a single lesson candidate present, run
`sr-agent lessons list/show/approve/dismiss`; confirm an approved candidate is written
into the knowledge corpus with an integrity signature that verifies, a tampered promoted
lesson fails verification, a dismissed candidate is never promoted, and there is no code
path by which the agent promotes a lesson without human approval.

**Acceptance Scenarios**:

1. **Given** a pending lesson candidate, **When** the operator runs `sr-agent lessons
   list`, **Then** the candidate is shown; `show <id>` displays its full content
   (trigger, symptom, fix, provenance, category).
2. **Given** a pending candidate, **When** the operator runs `lessons approve <id>`,
   **Then** the lesson is written into the retrievable knowledge corpus, carries an
   integrity signature that verifies, and is marked promoted.
3. **Given** a pending candidate, **When** the operator runs `lessons dismiss <id>`,
   **Then** it is removed from the queue and never enters the knowledge corpus.
4. **Given** a promoted lesson whose stored content is altered after promotion, **When**
   its integrity is verified, **Then** verification fails (tamper detected).
5. **Given** the running agent/harness, **When** its code paths are inspected, **Then**
   none can promote a candidate — promotion happens only through the out-of-band operator
   command (mirrors the `sr-agent confirm` guarantee).

---

### User Story 2 - Retrieve a promoted lesson at build time as a suggestion (Priority: P2)

As the operator, I need promoted lessons relevant to what the harness is currently doing
to be surfaced into the PoC draft/fix prompt as a **DATA-wrapped hint** — so the model
stops re-hitting a solved gotcha — while being **strictly a suggestion**: a retrieved
lesson can never become an instruction or alter control flow.

**Why this priority**: This is the payoff that turns curated knowledge into saved
metered-run time, but it depends on US1 having produced promoted lessons; it can be
delivered and tested with a manually promoted lesson.

**Independent Test**: With one promoted lesson in the corpus, exercise the harness
draft/fix prompt assembly; confirm the relevant lesson appears in the prompt wrapped as
data (`[DATA START]..[DATA END]`), that retrieval is scoped by relevance to the current
context, that it falls back to lexical ranking when no embedder is present, and that a
lesson's content cannot escalate into a control instruction.

**Acceptance Scenarios**:

1. **Given** a promoted lesson relevant to the current draft context, **When** the
   draft/fix prompt is assembled, **Then** the lesson is included, wrapped as data, as
   reference material only.
2. **Given** no relevant promoted lesson, **When** the prompt is assembled, **Then** no
   lesson block is added and behavior is identical to before the feature.
3. **Given** no embedding backend is available, **When** retrieval runs, **Then** it
   falls back to deterministic lexical ranking and adds no new runtime dependency.
4. **Given** a promoted lesson whose text contains instruction-like content, **When** it
   is retrieved into the prompt, **Then** it is presented as DATA and cannot alter the
   harness's control flow (the DATA-wrapping invariant holds).

---

### User Story 3 - Capture lessons automatically, deduplicated (Priority: P2)

As the operator, I need the harness to **automatically** propose a lesson candidate when a
run produces a reproducible signal (a previously-failing error-signature that got
resolved), and I need the same recurring signal to produce **one** queue item, not one per
occurrence — so the candidate queue reflects real distinct lessons and stays low-noise.

**Why this priority**: Automatic capture is what makes the loop "capture-always" rather
than manual data entry, but the gate (US1) and retrieval (US2) deliver value even if the
queue is seeded by hand, so capture is P2.

**Independent Test**: Drive the harness (offline, fake model/sandbox) through a
resolved-error transition; confirm exactly one candidate is emitted with the correct
fields; drive an identical resolved-error signal again and confirm no second queue item is
created (dedup by error-signature); confirm a capture failure never aborts the run.

**Acceptance Scenarios**:

1. **Given** the harness resolves a previously-failing error-signature, **When** the run
   proceeds, **Then** exactly one lesson candidate is emitted capturing the trigger
   signature, symptom, fix, provenance (`origin = llm_inference`), and category.
2. **Given** a candidate already queued for an error-signature, **When** the same
   error-signature is resolved again, **Then** no duplicate candidate is added (dedup by
   error-signature).
3. **Given** capture itself fails (e.g. the queue cannot be written), **When** it happens
   mid-run, **Then** the harness run continues unaffected (capture is best-effort,
   non-blocking).

---

### Edge Cases

- **Seeding**: the 13 confirmed gotchas in `docs/roadmap.md` are the initial promotable
  content. They are onboarded through the same promotion gate (proposed as candidates or
  directly authored by the operator), not written straight into the corpus by automation —
  the human-authority path is the only way in.
- **A candidate whose error-signature already matches a *promoted* lesson** → not
  re-queued (already-known); the loop must not re-propose what's already promoted.
- **An approved lesson the operator wants to edit** → the operator may amend the
  candidate's text before/at approval; the promoted, signed content is whatever the human
  approved (never silently model-authored).
- **Retrieval with an empty corpus** → returns nothing; the prompt path is byte-identical
  to pre-feature behavior.
- **A promoted lesson file altered on disk** → integrity verification flags it; a failing
  lesson is not silently trusted.
- **Capture producing a low-quality/near-empty candidate** → it still queues (the human
  filters at review); capture never blocks the run to judge quality.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST let the harness emit a lesson **candidate** — {trigger
  error-signature, symptom, fix, provenance, category, status} — when it resolves a
  previously-failing error-signature, without blocking or failing the run if capture
  itself errors.
- **FR-002**: Candidates MUST be **deduplicated by error-signature**: a recurring signal
  yields one queue item, not one per occurrence, and a signal already covered by a
  promoted lesson is not re-queued.
- **FR-003**: The system MUST provide an out-of-band `sr-agent lessons` command with
  `list`, `show`, `approve`, and `dismiss` subcommands, mirroring the shape and
  out-of-band guarantee of `sr-agent confirm` (it runs as a separate process from the
  agent loop).
- **FR-004**: A lesson MUST become part of the retrievable knowledge corpus **only** via
  human approval through that command; there MUST be no code path by which the agent or
  harness promotes a candidate itself.
- **FR-005**: A promoted lesson MUST be stored with a tamper-evident integrity signature
  (same HMAC scheme as append-only memory), so its integrity can be verified and any
  post-promotion alteration is detected.
- **FR-006**: A promoted lesson MUST carry a **category** so retrieval can be scoped, and
  MUST record two distinct facts: an immutable **`origin = llm_inference`** (a model
  drafted the text — honest audit) and, on promotion, **`authorization = human_input`**
  (the human's review-and-command act that admits it to the applied knowledge base, per
  Principle IV). Promotion sets `authorization` **without** rewriting `origin`;
  authorization governs KB membership only — a retrieved lesson is DATA-wrapped and can
  never act as an instruction regardless of tier (FR-007).
- **FR-007**: At build time, retrieval MUST surface promoted lessons relevant to the
  harness's current draft/fix context, **DATA-wrapped**, injected as reference only — a
  retrieved lesson MUST NOT be able to alter control flow or act as an instruction.
- **FR-008**: Retrieval MUST work without any embedding backend (deterministic lexical
  fallback) and MUST NOT introduce a new runtime dependency; an optional local embedder
  may improve ranking when present.
- **FR-009**: v1 MUST wire exactly one capture producer (the PoC-workability harness) and
  integrate retrieval only into the harness draft/fix prompt path; the audit loop as a
  producer and audit-analysis retrieval are out of scope.
- **FR-010**: All behavior MUST be verifiable **offline** — no model, Docker, network, or
  paid API — including capture, dedup, the CLI, signing/verification, and retrieval.

### Key Entities *(include if feature involves data)*

- **Lesson candidate**: a proposed, not-yet-trusted lesson awaiting human review —
  {trigger error-signature (dedup key), symptom, fix, provenance (low-trust source),
  category, status=pending}. Lives in the candidate queue.
- **Promoted lesson**: a human-approved lesson written into the retrievable knowledge
  corpus, carrying a tamper-evident integrity signature and a category; the only kind of
  lesson that retrieval will surface.
- **Candidate queue**: the pending-review store (analogous to the confirmations store),
  deduplicated by error-signature.
- **Error-signature**: the reproducible key identifying a distinct failure/lesson (the
  harness's existing compile/FAIL signature notion); both the dedup key and the retrieval
  relevance anchor.
- **Knowledge corpus**: the existing read-only, build-time reference store the harness
  consults; promoted lessons become entries in it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A resolved-error signal produces exactly **one** deduplicated candidate; a
  second identical signal adds **zero** further queue items.
- **SC-002**: `sr-agent lessons list/show/approve/dismiss` operate out-of-band with the
  same guarantee as `sr-agent confirm`; an approved lesson is retrievable, a dismissed one
  never is.
- **SC-003**: Every promoted lesson's integrity signature verifies; a tampered promoted
  lesson **fails** verification (100% tamper detection in test).
- **SC-004**: There is **no** code path by which the agent/harness promotes a lesson
  without human approval — asserted by test, mirroring the confirm out-of-band guarantee.
- **SC-005**: A retrieved lesson enters the draft/fix prompt **DATA-wrapped** as reference
  only and cannot escalate into an instruction or change control flow — asserted by test.
- **SC-006**: Retrieval succeeds with **no** embedding backend (lexical fallback) and adds
  **no** new runtime dependency; the full validation runs offline.
- **SC-007**: With an empty/irrelevant corpus, the harness draft/fix prompt is
  **byte-identical** to pre-feature behavior (the feature is additive and inert when unused).

## Assumptions

- The "user" is the maintainer/operator; this is internal capability, not an end-user
  feature. The human gate is the operator, exactly as for `sr-agent confirm`.
- "Resolved error-signature" (the capture trigger) means a compile/FAIL signature that was
  present on an earlier attempt in a finding's loop and is absent after a subsequent fix —
  reusing the harness's existing `_error_signature`/`_fail_signature` notion. The precise
  set of qualifying transitions is a design detail for planning; the behavior (one
  deduplicated candidate per distinct resolved signature) is fixed here.
- The knowledge corpus is the existing build-time reference store
  (`sr_agent/memory/knowledge.py` over the `knowledge/` tree); promoted lessons are a new
  category of entries in it, retrieved by the same mechanism. Promoted lessons are **pack
  content**; the capture/queue/gate/sign/retrieve **mechanism** is kernel.
- The integrity signature reuses the append-only memory HMAC scheme
  (`config.secret_key`), so `verify`-style integrity checking extends naturally to lessons.
- Retrieval into the harness draft/fix path is the only v1 integration; the DATA-wrapping
  rule and the trust hierarchy are **relied upon, not modified** by this feature.
- Seed content: the 13 confirmed gotchas already recorded in `docs/roadmap.md` are the
  initial promotable lessons, onboarded through the human gate.
- This is roadmap Phase 6; it depends on the already-landed Phase 4 kernel/pack boundary
  and the memory/knowledge subsystem. A second producer (audit loop) and free-form
  (non-signature-keyed) lessons are explicitly deferred to v2.
