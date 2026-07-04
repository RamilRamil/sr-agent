# Data Model: Interactive Chat Mode

Two genuinely new entities (`ChatSession`, `ChatTurn`); everything else reuses existing models unmodified. Field names below are the concrete Pydantic fields to implement in `sr_agent/models/chat.py`, not the abstract spec-language versions.

## ChatSession

Maps to the spec's **Chat Session** entity. Persisted as `MemoryRecord`s under `target=f"chat:{session_id}"` (R5) — this model is the reconstructed, in-memory view after loading those records, not itself a storage format.

| Field | Type | Notes |
|---|---|---|
| `session_id` | `str` (uuid4 default) | Identity; matches the `session:{id}` / `chat:{id}` target-key convention already used for audit checkpoints. |
| `principal` | `Principal` (existing model, reused) | `user_id`, `platform`, `project_id` — establishes the one-project binding required by FR-001. |
| `started_at` | `datetime` | |
| `status` | `"active" \| "paused_confirmation" \| "paused_relay" \| "blocked_local_unavailable"` | Drives what `sr-agent chat` prints on resume and whether a turn can proceed without external action first. |
| `pending_confirmation_id` | `str \| None` | Set when `status == "paused_confirmation"`; the confirmation id the user must resolve via `sr-agent confirm` before resuming. |
| `pending_relay_request_id` | `str \| None` | Set when `status == "paused_relay"`; mirrors the Stage 2 relay manifest pattern. |
| `turn_ids` | `list[str]` | Ordered list of `ChatTurn.turn_id`, for reconstructing history order from unordered `EpisodicMemory.load()` results. |
| `session_facts` | `SessionFacts` (below) | The deterministic, orchestrator-authored grounding-fact store (R6) — never LLM-authored. |

**Validation rules**:
- `principal.project_id` MUST be non-empty and MUST match the project the session was opened against — FR-001's "no implicit switching between projects mid-session" is enforced by simply never accepting a different `project_id` into an existing session's turns.
- A session with `status != "active"` MUST reject new user input other than a resume/status-check until its pending item resolves — this is the mechanical form of FR-011 (refuse and wait) and R8 (pending confirmation blocks new turns, not the process).

## SessionFacts

The R6 grounding-fact bucket. Deliberately small and deterministic — not a transcript.

| Field | Type | Notes |
|---|---|---|
| `project_id` | `str` | Redundant with `ChatSession.principal.project_id` by design — this is the copy that gets wrapped into every turn's prompt via `context.wrap_data`, independent of whatever the model currently believes. |
| `known_finding_ids` | `list[str]` | Updated whenever a finding is persisted (by the orchestrator, not the model) — mirrors `AuditSession.finding_ids`. |
| `recent_tool_summaries` | `list[str]` (bounded, e.g. last 10) | One short orchestrator-written line per notable tool result (e.g. `"read_file contracts/Foo.sol (312 lines)"`), not the full tool output — the full output already lives in the turn's own `MemoryRecord` if it needs re-reading. |

**Validation rules**:
- Every write to `SessionFacts` MUST originate from the orchestrator (i.e., from `_dispatch`/`_persist_finding`-equivalent code), never from parsing model output directly into this structure — this is the trust property R6 depends on.

## ChatTurn

Maps to the spec's **Turn** entity. One per user message; persisted as a `MemoryRecord` with `target=f"chat:{session_id}"`.

| Field | Type | Notes |
|---|---|---|
| `turn_id` | `str` (uuid4 default) | |
| `session_id` | `str` | Foreign key into `ChatSession`. |
| `user_message` | `str` | Raw user text — this is `human_input` trust tier by construction (it's the CLI operator typing), but per spec Edge Cases, the CONTENT of this message is not thereby granted authority over memory-record status changes; only the out-of-band `sr-agent confirm`/`memory` commands carry that. |
| `routing_decision` | `RoutingDecision` (below) | |
| `agent_action` | `AgentAction` (existing model, reused, unmodified) | The literal decision output — no new decision schema, per FR-002/FR-003. |
| `tool_invocations` | `list[ToolInvocation]` (below) | Zero or more, capped by the per-turn budget (R4). |
| `source_type` | `SourceType` (existing enum, reused) | Set to `external_llm_output` for the turn's `agent_action`/findings (R7) — never `llm_inference`, never promoted to `human_input` regardless of turn count (FR-007). |
| `completed_at` | `datetime \| None` | Null while the turn is mid-flight (e.g., paused on confirmation). |

**Validation rules**:
- `len(tool_invocations) <= per_turn_tool_budget` MUST hold at all times — this is FR-006 as a structural invariant, not just a runtime check.
- If `agent_action.next_action` is a `write_execute`-class action, the turn MUST have gone through `ChatSession.status == "paused_confirmation"` before `completed_at` is set — no `write_execute` `ChatTurn` can be marked complete without a corresponding approved confirmation record existing in `confirmations/`.

## RoutingDecision

Maps to the spec's **Routing Decision** entity. Not persisted as its own record type — embedded in `ChatTurn`, but broken out here because it's the FR-010 "which tier produced this" answer.

| Field | Type | Notes |
|---|---|---|
| `tier` | `"local" \| "relay" \| "blocked_local_unavailable"` | R2/R10: never a third silent-fallback tier — `blocked_local_unavailable` is a terminal-for-this-turn state, not something that becomes `relay` automatically. |
| `escalation_trigger` | `EscalationTrigger \| None` (existing enum, reused) | Set when `evaluate_triggers()` (R3) or the model's own self-report fired — whichever fired first is recorded; both being independently checkable is what makes this auditable. |
| `escalation_source` | `"model_self_report" \| "deterministic_guard" \| None` | Which of the two (R3) actually caused escalation — useful for auditing whether the deterministic guard is the one doing the real work, which is the intended design. |

## ToolInvocation

Maps to part of the spec's **Turn** entity (tool calls within a turn). Not a new persisted record type — embedded in `ChatTurn`; reuses `Action`/`ActionType`/`ValidationResult` (existing, `models/action.py`) for the action itself.

| Field | Type | Notes |
|---|---|---|
| `action` | `Action` (existing model, reused) | |
| `validation_result` | `ValidationResult` (existing model, reused) | Output of `validate_action` — approved/rejected + reason. |
| `result_summary` | `str` | The DATA-wrapped (`wrap_data`) tool output as actually fed back into the next model call — persisted so a resumed session can reconstruct exactly what the model saw, not just what happened. |

## PoCStatusEvent (findings roadmap, R12)

The memory-backed progress record. Each event is an append-only `MemoryRecord` (`tool_output` tier, orchestrator-authored) under the session/project target key; the source of truth is signed episodic memory, and the human-readable roadmap table is a regenerable *view* over these events (never a parallel store). Kernel mechanism; audit-pack content.

| Field | Type | Notes |
|---|---|---|
| `finding_id` | `str` | The finding OR lead this row tracks. Every finding AND every lead gets one — no silent omission (no-lead-prefiltering rule). |
| `status` | `"pending" \| "written" \| "compiled" \| "passed" \| "failed" \| "errored" \| "skipped"` | Strictly mechanical PoC lifecycle. `passed` = "a reproduction exists", NOT "finding confirmed/safe". |
| `skip_reason` | `str \| None` | REQUIRED when `status == "skipped"` (e.g. `"floor-gated, out of scope"`) — a skip is an explicit reasoned row, never absence. |
| `poc_path` | `str \| None` | `audit/poc/<ident>.t.sol` once `written`. |
| `source_type` | `SourceType` | `tool_output` — orchestrator-authored from a real tool result, never `human_input`. |

**Validation rules**:
- `status` transitions only within the mechanical lifecycle; it MUST NOT encode a security verdict. Flipping a finding to `verified_safe`/`audit_complete` is a separate `REQUIRES_HUMAN_CONFIRMATION` action, not a roadmap status.
- A `PoCStatusEvent` write MUST originate from the orchestrator (from `run_tests`/`write_poc` result handling), never from parsing model output — same trust property as `SessionFacts` (R6/R12).

## ConsequentialActionNotice

Maps to the spec's **Consequential Action Notice** entity. Per R8, this is not a separate blocking record — it's the chat-visible text rendered the moment a `ChatTurn`'s `agent_action` resolves to a `write_execute`-class action and `request_confirmation` is called. Modeled here only to make explicit what it contains, since FR-008 requires it be shown "before or as it happens":

| Field | Type | Notes |
|---|---|---|
| `action_type` | `ActionType` (existing enum, reused) | |
| `action_params` | `dict` | Echoed from `Action.params` so the user can see exactly what will run (e.g., which `finding_id`) without needing to inspect the confirmation file separately. |
| `confirmation_id` | `str` | The id the user needs for `sr-agent confirm <id> --approve`. |
| `shown_at` | `datetime` | For FR-008's "before or as it happens" — this MUST be set before `check_confirmation` is ever polled, not after. |

## State transitions — ChatSession.status

```text
active ──(agent_action requires OOB confirmation)──> paused_confirmation
active ──(evaluate_triggers or self-report escalation)──> paused_relay
active ──(LocalClient.ready() == False mid-turn — deep generate-probe, not just available(), R10)──> blocked_local_unavailable

paused_confirmation ──(sr-agent confirm --approve, session resumed)──> active
paused_confirmation ──(sr-agent confirm --reject / timeout, session resumed)──> active
                         (turn completes with a rejection outcome fed back as DATA, per loop.py's
                          existing "not executed" observation pattern — the session is NOT stuck)

paused_relay ──(sr-agent relay --respond, session resumed)──> active
                (reuses orchestrator/relay.py + the Stage-2 manifest idempotency pattern —
                 a resumed session never double-submits a relay request for the same turn)

blocked_local_unavailable ──(local model becomes available again, next resume/turn attempt)──> active
                              (FR-011: automatic once available, no manual unblock action needed)
```

No transition ever moves a session from any `paused_*`/`blocked_*` state directly into treating the eventual external input (confirmation, relay response, restored local model) as `human_input`-tier authority over anything beyond the specific pending item it resolves — resolving a confirmation approves *that action*, it does not retroactively upgrade the trust tier of anything else in the session (FR-007).
