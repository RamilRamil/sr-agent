# Implementation Plan: Interactive Chat Mode

**Branch**: `003-interactive-chat-mode` | **Date**: 2026-07-02 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-interactive-chat-mode/spec.md`

## Summary

Add `sr-agent chat <project>`: a persistent, resumable REPL that drives the **existing but currently orphaned** `OrchestratorLoop` (`orchestrator/loop.py`) instead of introducing a new decision/execution path. That loop already does everything FR-004/FR-005/FR-006 require (DATA-wrapping, `validate_action`, out-of-band confirmation) — it has just never been wired to anything live. The work is: (1) replace its hardcoded `ClaudeClient` (paid API) with a routing provider that tries the local model first and only escalates to the manual relay on a deterministic trigger, never as a silent fallback; (2) turn its whole-session `MAX_ITERATIONS` cap into a per-turn tool-call budget that resets every user message; (3) implement the `write_execute` dispatch branch it currently stubs out, so `write_poc`/`run_tests` actually run (gated by the confirmation flow that's already there, not bypassed the way `scripts/poc_queue_runner.py` bypassed it); (4) wire in `guardrails/escalation.py::evaluate_triggers`, which is also built and also never called anywhere; (5) fix `_persist_finding`'s `source_type` from `llm_inference` to `external_llm_output` so chat findings match the trust tier every other model-originated finding in the system already uses; (6) add a small `ChatSession` persistence layer reusing `EpisodicMemory` exactly the way `checkpoint.py` already does, for FR-012 resumability.

No new trust primitives, no new action types, no new storage technology — this is a wiring and correction pass over code that was already built for exactly this purpose and left disconnected.

## Technical Context

**Language/Version**: Python 3.14 (matches existing `.venv`, `sr_agent/` package)

**Primary Dependencies**: `click` (CLI, existing `cli.py` pattern), `pydantic` (existing schemas), stdlib `urllib`/`subprocess` (existing `LocalClient`, `DockerSandbox` — no new HTTP/process deps)

**Storage**: Existing `EpisodicMemory` (HMAC-signed, append-only JSONL per project/target) — chat sessions and turns persist as `MemoryRecord`s under a session-scoped target key (`chat:{session_id}`), the same pattern `checkpoint.py` already uses for audit-session checkpoints. No new storage technology.

**Testing**: `pytest`, run via `PYTHONPATH=. .venv/bin/python -m pytest` (existing project convention); new tests live under `tests/unit/` and `tests/integration/` alongside the existing `test_action_validation.py`, `test_oob_confirmation.py`, etc.

**Target Platform**: CLI on macOS/Linux — same as the rest of `sr-agent` (`cli.py`), no new platform surface.

**Project Type**: Single Python package (`sr_agent/`) with a CLI entry point — extends the existing structure, not a new project.

**Performance Goals**: Not latency-critical (single-user interactive REPL, not a service). The one measurable constraint is SC-004 (95% grounding-fact consistency across a session long enough to exceed the local model's ~28K-token window per `context.py::CONTEXT_LIMITS`).

**Constraints**: Must reuse `validate_action`/`REQUIRES_OOB_CONFIRMATION`/`request_confirmation`/`check_confirmation` unmodified for gating (FR-005); must not add a second AgentAction-shaped decision format (FR-002/FR-003); local-model-unavailable must refuse-and-wait, never silently fall back to relay (FR-011, user-confirmed).

**Scale/Scope**: Single user, one project/audit session bound per chat session (FR-001). Multiple concurrent sessions on different projects are out of scope for acceptance criteria (spec Assumptions).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against constitution v1.0.0 (ratified 2026-07-02). This feature is effectively the reference implementation of the kernel principles, and passes each:

- **I. Secure-Kernel Trust Invariants** — reuses `context.wrap_data` (DATA on every turn), the `SourceType` hierarchy, HMAC `EpisodicMemory`, and adds the per-turn tool budget (R4); R7 fixes a trust-tier bug (`llm_inference` → `external_llm_output`) rather than importing it. PASS.
- **II. Human Authority** — reuses `validate_action`/`REQUIRES_OOB_CONFIRMATION`/`confirmation.py` unmodified; R8 confirms no soft-gate bypass; PoC `passed` never flips a finding verdict (poc-execution contract). PASS.
- **III. Kernel/Pack Separation** — additions are placed by side: readiness probe R10 = kernel (`local_client.py`); PoC-execution R11 + roadmap-content R12 = audit-pack (`contracts/poc-execution.md`, not `loop.py`). No plugin registry (YAGNI). PASS.
- **IV. Human-Gated Knowledge** — the roadmap (R12) records mechanical status only; no tool-output-derived observation self-promotes into steering knowledge. PASS.
- **V. No Paid-API Dependency** — R2: local-first, relay on deterministic escalation only; `claude_client.py` untouched and unimported by the chat path. PASS.

No violations to justify; Complexity Tracking omitted.

## Project Structure

### Documentation (this feature)

```text
specs/003-interactive-chat-mode/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/            # Phase 1 output
│   ├── cli-chat-command.md
│   ├── chat-turn-contract.md
│   └── poc-execution.md   # audit-pack: Foundry profile, audit/poc/ output, via_ir, status→roadmap
└── tasks.md              # Phase 2 output (/speckit-tasks — not this command)
```

### Source Code (repository root)

```text
sr_agent/
├── cli.py                          # ADD: `chat` command (new subcommand, alongside audit/resume/confirm/relay)
├── orchestrator/
│   ├── loop.py                     # MODIFY: swap ClaudeClient for ChatReasoningProvider;
│   │                                #   MAX_ITERATIONS -> per-turn budget; implement write_execute
│   │                                #   dispatch (was a stub); wire evaluate_triggers; fix source_type
│   ├── action.py                   # REUSE unmodified — validate_action, REQUIRES_OOB_CONFIRMATION
│   ├── confirmation.py             # REUSE unmodified — request_confirmation, check_confirmation
│   ├── context.py                  # EXTEND — add a session-facts bucket to build_messages()
│   │                                #   truncation priority (highest, never dropped)
│   ├── checkpoint.py                # PATTERN REUSE — chat_session.py follows this shape
│   └── chat_session.py             # NEW — ChatSession persistence (save_turn/load_session),
│                                    #   same MemoryRecord-over-EpisodicMemory pattern as checkpoint.py
├── llm_core/
│   ├── chat_reasoning.py            # NEW — ChatReasoningProvider: local-first .complete(messages)->AgentAction,
│   │                                #   refuse-and-wait on local-unavailable, relay pause/resume on
│   │                                #   deterministic escalation only
│   ├── local_client.py             # REUSE unmodified — LocalClient.generate/available
│   └── claude_client.py            # UNCHANGED, untouched by chat mode (still used by non-chat Stage1/3 path
│                                    #   if/when that's wired; chat never imports it)
├── guardrails/
│   └── escalation.py               # REUSE unmodified — evaluate_triggers (now actually called)
├── models/
│   └── chat.py                     # NEW — ChatSession, ChatTurn Pydantic models
└── tools/
    ├── write_execute.py            # REUSE unmodified — write_poc, run_tests
    └── sandbox.py                  # REUSE unmodified — DockerSandbox

tests/
├── unit/
│   ├── test_chat_session.py        # NEW
│   ├── test_chat_reasoning.py      # NEW
│   └── test_orchestrator_loop_chat.py  # NEW — per-turn budget, write_execute dispatch, evaluate_triggers wiring
├── integration/
│   └── test_chat_cli.py            # NEW — sr-agent chat end-to-end: Q&A turn, PoC-request turn
│                                    #   (OOB-gated), resume-after-restart
└── security/
    └── test_chat_mi_scenarios.py   # NEW — reuses tests/security/mi_scenarios.py harness against chat turns
                                     #   (embedded-instruction tool output, prior-turn "mark this safe" attempt)
```

**Structure Decision**: Extends the existing single-package `sr_agent/` layout. No new top-level projects, no frontend/backend split — this is a new CLI subcommand plus a handful of new modules (`orchestrator/chat_session.py`, `llm_core/chat_reasoning.py`, `models/chat.py`) that sit next to and reuse the existing orchestrator/tools/memory modules, mirroring how `planner/stage2.py` already sits next to `orchestrator/relay.py` and reuses it.

## Complexity Tracking

*No constitution violations to justify — table intentionally omitted (see Constitution Check above).*
