# Implementation Plan: Two-Agent Audit Sessions with an Audit-File Input

**Branch**: `019-two-agent-audit-sessions` | **Date**: 2026-07-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/019-two-agent-audit-sessions/spec.md`

## Summary

Three grounded gaps, one feature. (US1) Session creation gains an optional external `audit_path`; its content is read, `wrap_data`-wrapped as untrusted `[DATA]`, and folded into the session grounding via the existing `session_facts_provider → build_messages(session_facts=…)` path (which already DATA-wraps). (US2) The existing single model config is formalized as the "main" slot (local/Gemini via `reasoning_client()` — already built). (US3) A second "additional" config slot is added; `ChatReasoningProvider._escalate` is rewired so that, when an additional client is configured, escalation calls it (reusing the `generate()`-duck client: local or Gemini) and returns a normal actionable outcome that flows through `run_turn`'s existing action path — so the confirmation gate (`request_confirmation`) and the `external_llm_output` trust status both apply unchanged. With no additional agent configured, `_escalate` falls back to today's file relay verbatim. Stage 2's own `request_analysis` use is untouched.

## Technical Context

**Language/Version**: Python 3.11 (backend) + Svelte/TS (UI).

**Primary Dependencies**: none new. Reuses `GeminiClient` (spec 018), `LocalClient`, `wrap_data`/`build_messages`, `request_analysis`, `request_confirmation`. `google-genai` stays the only optional extra.

**Storage**: none new. Report content is read from the external path at session start and held in memory for the session; keys stay write-only in-process (spec-018 pattern).

**Testing**: pytest, offline/deterministic. Fake clients + monkeypatched escalation; an injection-style test for report-as-DATA. No real key, no network.

**Target Platform**: operator frontend process + `sr_agent` orchestrator/llm_core.

**Project Type**: single project — backend wiring + one Svelte settings/session change.

**Performance Goals**: n/a (turn latency is the model's).

**Constraints**: report content is bounded by a length budget and DATA-wrapped; additional-agent output is `external_llm_output` and its proposed actions still hit the confirmation gate; keys write-only; core session runs with local main, no additional, no report (no hosted dependency).

**Scale/Scope**: ~2 backend modules edited (`sessions.py`, `model_config.py`, `app.py`), 1 orchestrator client edited (`chat_reasoning.py`), 2 Svelte panels, ~5 test files, docs.

## Constitution Check

*GATE: evaluated against the 5 principles. Re-checked after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Secure-Kernel Trust Invariants** | ✅ PASS | The report is included ONLY through `wrap_data` (untrusted `[DATA]`, same path as `session_facts`/tool output) — it can describe reality but never override instructions. The additional agent's output flows through `ChatTurn`, which stamps `external_llm_output`; the `SourceType` ordering is unchanged. |
| **II. Human Authority** | ✅ PASS | The additional agent returns a normal `AgentAction` that re-enters `run_turn`'s existing action path — so any privileged/irreversible action still routes through `request_confirmation` (already inside `run_turn`, confirmed by codegraph `callees run_turn`). Auto-escalation cannot execute a gated action; it only produces a proposal. |
| **III. Kernel / Pack Separation** | ✅ PASS | Changes are in `llm_core` (a reasoning client), the orchestrator composition, and the frontend — no pack coupling added. Stage 2's `request_analysis` use is untouched (codegraph showed it shares the relay; we rewire only `_escalate`). |
| **IV. Human-Gated Knowledge Promotion** | ✅ PASS | Escalation output stays `external_llm_output`; it is never self-promoted into steering knowledge. No knowledge-loop change. |
| **V. No Paid-API Dependency** | ✅ PASS | Main AND additional can both be local; Gemini stays the optional extra; with no additional agent configured the escalation falls back to the file relay. A session with a local main, no additional, no report runs fully offline — a test proves it. |

**Result: PASS — no violations. Complexity Tracking not required.**

Design note (II, the sensitive point): making escalation auto-call a model does NOT weaken the human gate, because the additional agent produces an `AgentAction` proposal that traverses the identical validate→confirm path the main agent's proposals do. The only thing that changes is *who authored the proposal text* (a configured model instead of a human-relayed one) — and both are `external_llm_output`.

## Project Structure

### Documentation (this feature)

```text
specs/019-two-agent-audit-sessions/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/two-agent-sessions.md
└── tasks.md   # /speckit-tasks
```

### Source Code (repository root)

```text
frontend/backend/
├── model_config.py   # EDIT: two named slots (MAIN, ADDITIONAL); each a ModelConfig; additional_client() -> client|None
├── app.py            # EDIT: /api/model/config → both slots; /api/session gains audit_path
└── sessions.py       # EDIT: start(project_path, audit_path?); build report facts provider + additional client; pass to provider

sr_agent/llm_core/
└── chat_reasoning.py # EDIT: ChatReasoningProvider gains `additional` client; _escalate calls it (fallback: relay)

sr_agent/orchestrator/
└── (loop.py unchanged — session_facts_provider already the injection seam; sessions.py supplies it)

frontend/ui/src/panels/
├── Settings.svelte     # EDIT: Main agent + Additional agent panels (method/endpoint/model/key each)
└── ChatSession.svelte  # EDIT: audit-file path field on session create
frontend/ui/src/lib/api.ts  # EDIT: session create carries audit_path; two-slot model config

tests/
├── unit/test_report_context.py        # NEW: report read → wrap_data → included; budget; external-path reject
├── unit/test_agent_slots.py           # NEW: main+additional slot config; key write-only; additional_client() None when unset
├── integration/test_additional_agent_escalation.py  # NEW: escalation consults additional (fake), output external_llm_output, confirmation gate preserved; no-additional → relay fallback
├── security/test_report_not_instruction.py  # NEW: report text with an embedded instruction is not obeyed
└── (reuse) frontend/test_no_paid_api.py stays green

docs/roadmap.md  # EDIT: spec 019 landing entry
```

**Structure Decision**: Reuse everything. Report injection rides the existing `session_facts` DATA path (no new context primitive). The additional agent reuses the `generate()`-duck clients (`LocalClient`/`GeminiClient`) already present; escalation returns an `AgentAction` so the confirmation gate and trust status are inherited, not re-implemented. Two config slots are two `ModelConfig` instances, not a new config type.

## Complexity Tracking

No constitution violations — section intentionally empty.
