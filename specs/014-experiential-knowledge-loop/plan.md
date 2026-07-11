# Implementation Plan: Experiential Knowledge Loop (v1)

**Branch**: `014-experiential-knowledge-loop` | **Date**: 2026-07-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/014-experiential-knowledge-loop/spec.md`

## Summary

Close the learning loop (roadmap Phase 6) so the project stops re-discovering the same
reproducible lessons every metered run — **under human authority**. The harness *proposes*
a lesson candidate when it resolves a previously-stuck error-signature; the candidate lands
in a deduplicated queue; the operator *promotes* it via a new out-of-band `sr-agent
lessons` CLI (mirroring `sr-agent confirm`); promotion writes an HMAC-signed lesson into
the existing `knowledge/` corpus; on the next run the harness's draft/fix prompt retrieves
relevant promoted lessons **DATA-wrapped, as suggestion not control**. The mechanism
(capture/queue/gate/sign/retrieve) is kernel; the lesson content is pack. Every primitive
is reused (confirmation store pattern, `memory/hmac.py`, `KnowledgeBase`, the harness's
existing `_error_signature`/`prev_*` tracking); no new runtime dependency; all validation
offline.

## Technical Context

**Language/Version**: Python 3.11+ (existing codebase).

**Primary Dependencies**: none new. Reuses `sr_agent/memory/hmac.py` (sign/verify),
`sr_agent/memory/knowledge.py` (`KnowledgeBase.search`, lexical + optional local embedder),
the confirmation-store pattern (`sr_agent/orchestrator/confirmation.py`), `click` (already
the CLI framework), and the harness's existing signature/loop machinery in
`scripts/poc_queue_runner.py`.

**Storage**: files only — `lessons/pending/<sig_id>.json` (unsigned candidate queue,
analogous to `confirmations/`); `knowledge/lessons/<sig_id>.md` + a signed
`knowledge/lessons/_manifest.jsonl` (HMAC per promoted lesson). Same `config.secret_key`
as episodic memory.

**Testing**: pytest, offline. Reuses the spec-009 offline fake-model/fake-sandbox harness
for the capture integration test. New tests across `tests/unit`, `tests/integration`,
`tests/architecture`, `tests/security`. No model, Docker, network, or paid API (FR-010).

**Target Platform**: local dev machine; CI-safe.

**Project Type**: single project — a small kernel module (lesson store + capture API +
promotion/sign + retrieval wrapper), a new `sr-agent lessons` CLI command, one non-blocking
capture hook + one retrieval hook in the harness.

**Performance Goals**: N/A (capture is a best-effort file write; retrieval is the existing
lexical scorer over a small corpus).

**Constraints**: capture MUST be non-blocking (a failure never aborts a run, FR-001);
promotion MUST be out-of-band-only (no agent/harness code path promotes, FR-004/SC-004);
retrieval MUST be inert when the corpus is empty (byte-identical prompt, SC-007); no new
dependency (FR-008); DATA-wrapping and the trust hierarchy are **relied upon, not
modified**.

**Scale/Scope**: one kernel module (~ lesson model + store + sign + retrieve), one CLI
command with four subcommands, two harness hooks (capture, retrieve), seed onboarding of
the 13 gotchas through the gate, and the test suite above.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Secure-Kernel Trust Invariants** — PASS, and this feature is a direct application
  of them. Promoted lessons are **DATA-wrapped on retrieval (never obeyed as instructions),
  regardless of authorization tier** — Principle I DATA-wraps every artifact re-entering
  context. A lesson records an immutable `origin = llm_inference` (honest audit that a
  model drafted it); the human's promotion grants `authorization = human_input` per
  Principle IV (see below), which governs KB membership, **not** instruction-power. These
  are two distinct facts, never conflated; Principle I's "model output must never be
  promoted to `human_input`" concerns the *running-loop trust of tool/model artifacts*, not
  the *human-commanded knowledge-promotion* path Principle IV explicitly authorizes.
  Promoted lessons are HMAC-signed and dropped-silently on verify failure. No trust/
  `SourceType`/DATA-wrap rule is modified — all are reused.
- **II. Human Authority for Privileged & Irreversible Actions** — PASS. Promotion is an
  out-of-band human act (the `sr-agent lessons approve` CLI, separate process from the
  agent loop); no model turn can promote. Structurally identical to the confirmation gate.
- **III. Kernel / Capability-Pack Separation** — PASS. The capture/queue/gate/sign/
  retrieve **mechanism** is task-agnostic kernel; the **content** (smart-contract PoC
  lessons, the `poc-*` categories) is pack. No dynamic plugin registry (YAGNI) — v1 wires
  exactly one producer.
- **IV. Human-Gated Knowledge Promotion** — PASS; this feature **is** the implementation
  of Principle IV. Observations derived from tool output (error text) never self-promote;
  only the human's review-and-command elevates a candidate into the retrievable corpus.
  This is precisely the "collapses retrospective-poisoning risk to zero" design.
- **V. No Paid-API Dependency** — PASS. Capture, gate, sign, and retrieval are offline;
  retrieval's lexical fallback needs no model; the optional local embedder is
  Ollama-only. No paid API anywhere; all validation offline (FR-010).

No violations — **Complexity Tracking is empty**. This is squarely the constitution's
"Development Workflow & Quality Gates" (test-first for security-critical behavior: the
human-gate, tamper-evidence, and DATA-wrap guarantees are each written as a failing test
first).

## Project Structure

### Documentation (this feature)

```text
specs/014-experiential-knowledge-loop/
├── plan.md              # This file
├── research.md          # Phase 0 output (R1–R6)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (lesson lifecycle, CLI, retrieval)
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
sr_agent/memory/
├── lessons.py                    # NEW (kernel): Lesson/Candidate models, LessonStore
│                                 #   (candidate queue write+dedup; promote+HMAC-sign;
│                                 #    verify; category-scoped retrieve over KnowledgeBase)
├── hmac.py                       # REUSED unchanged (sign/verify)
└── knowledge.py                  # REUSED unchanged (KnowledgeBase.search)

sr_agent/cli.py                   # NEW `lessons` command: list/show/approve/dismiss
                                  #   (the ONLY caller of LessonStore.promote — out-of-band)

scripts/poc_queue_runner.py       # TWO hooks:
                                  #   (a) capture: on a resolved-error-sig transition in
                                  #       _process_finding, best-effort emit a candidate
                                  #   (b) retrieve: draft()/fix() prompt assembly appends a
                                  #       DATA-wrapped lessons block when relevant (inert if none)

knowledge/lessons/                # NEW corpus area: <sig_id>.md + _manifest.jsonl (signed)
lessons/pending/                  # NEW candidate queue (runtime, untracked)

tests/
├── unit/test_lessons_store.py            # candidate dedup, promote+sign, verify, tamper
├── integration/test_lessons_capture.py   # _process_finding resolved-sig → one candidate
│                                          #   (reuses spec-009 fake model/sandbox)
├── integration/test_lessons_retrieve.py  # draft/fix prompt gains DATA-wrapped block;
│                                          #   inert when empty; lexical fallback
├── architecture/test_lessons_promote_gate.py  # no self-promotion: promote() unreferenced
│                                               #   by harness/orchestrator (AST, like 013)
└── security/test_lesson_not_instruction.py    # a lesson cannot escalate to control
```

**Structure Decision**: Single project. One new kernel module (`sr_agent/memory/lessons.py`)
holds the mechanism (models + store + sign + verify + category-scoped retrieval wrapper
over the existing `KnowledgeBase`). The human gate is a new `sr-agent lessons` CLI command
— the **only** caller of `promote()`, exactly as `sr-agent confirm` is the only writer of
"approved". The harness gets two small, additive hooks (non-blocking capture; inert-when-
empty retrieval). Promoted content lives under `knowledge/lessons/` so the existing
`KnowledgeBase` reads it unchanged; a signed side-manifest carries the HMAC.

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*

**Post-design re-check (after Phase 0/1)**: research.md's decisions (two stores; reuse
`hmac.py`; capture at the resolved-sig transition; retrieve via `KnowledgeBase` DATA-
wrapped; out-of-band-only promotion pinned by a test; all offline) introduce **no** new
violations — still PASS, and US1/US2 strengthen Principles I, II, and IV.
