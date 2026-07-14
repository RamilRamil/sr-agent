# Research: Two-Agent Audit Sessions (spec 019)

Grounded in a fresh codegraph over the repo (2140 nodes / 5154 edges) + direct reads. The graph misses instance-method call edges, so those were verified by grep.

## Decision 1: Inject the report through the existing `session_facts` DATA path

**Decision**: The frontend supplies a `session_facts_provider` to the `OrchestratorLoop` that returns the DATA-relevant grounding INCLUDING the (budgeted) report text; `build_messages` already `wrap_data`-wraps `session_facts`, so the report is included as untrusted `[DATA]` with no new context primitive.

**Rationale**: Verified: `run_turn` does `facts = self._session_facts_provider(); build_messages(session_facts=facts, …)`, and `build_messages` wraps `session_facts` via `wrap_data(tool="session_facts")` at highest priority. Routing the report here means it is (a) DATA-wrapped for free (Constitution I), (b) budget-truncated by the existing priority logic. The frontend's `SessionManager` currently passes NO facts provider, so we add one that carries the report.

**Alternatives considered**: a new `report_context` param on `build_messages` (rejected — duplicates the session_facts DATA slot); storing the report in the AuditSession model (rejected — the report is chat grounding, not audit-input source; keep it in the facts provider).

## Decision 2: The additional agent returns an `AgentAction`, reusing `run_turn`'s gate

**Decision**: `ChatReasoningProvider._escalate`, when an additional client is configured, calls `additional.generate(rendered_context, fmt="json")`, parses it as an `AgentAction` (same strict parse as the main path), and returns `ReasoningOutcome(kind="action", agent_action=…, tier="additional")`. That outcome re-enters `run_turn`'s normal action handling — so `request_confirmation` and the `external_llm_output` `ChatTurn` status apply unchanged. With no additional client, it returns today's `kind="paused_relay"` via `request_analysis` (verbatim fallback).

**Rationale**: This is the crux for Constitution II. By making the additional agent emit the SAME `AgentAction` contract the main agent uses, the human-confirmation gate is inherited, not bypassed — codegraph confirmed `request_confirmation` is already a callee of `run_turn`, so any privileged action the additional agent proposes still pauses. The additional agent only changes *who authored the proposal*, both `external_llm_output`.

**Alternatives considered**: returning free-form escalation text to the operator without an AgentAction (rejected — then it can't propose actions uniformly, and we'd need a second gate path); auto-executing the additional agent's action (rejected — bypasses the gate, violates II).

## Decision 3: Additional-agent methods = {local, gemini} for v1 (Claude deferred)

**Decision**: The additional slot supports connection methods `local` and `gemini` in v1 — both expose `generate(prompt, fmt) -> str` and are drop-in. Claude is deferred: `ClaudeClient` exposes `.complete(messages) -> AgentAction` (structured, tracing-oriented), not a `generate()->str`, so wiring it needs a thin text-generate adapter — out of scope for v1.

**Rationale**: The spec's FRs say "local or hosted" (Gemini is the integrated hosted option, spec 018); it does not require Claude specifically. Scoping v1 to the two `generate()`-duck clients avoids a `ClaudeClient` adapter and keeps the change surgical. Claude is a clean follow-up (add `ClaudeClient.generate_text` or an adapter).

**Alternatives considered**: add a `ClaudeClient.generate_text` now (deferred — extra surface for a provider the operator can already reach via the manual relay fallback).

## Decision 4: Two config slots = two `ModelConfig` instances

**Decision**: Generalize the process-wide `CONFIG` into `MAIN` and `ADDITIONAL` (both `ModelConfig`). `MAIN` keeps today's behavior (`reasoning_client()`); `ADDITIONAL` adds `additional_client() -> LocalClient|GeminiClient|None` returning `None` when unconfigured (method unset or, for gemini, no key). `public()` per slot exposes only `has_paid_key` (write-only key preserved, spec 018).

**Rationale**: Reuses the spec-018 `ModelConfig` (endpoint/model/backend/_paid_key + reasoning_client) rather than inventing a new config type. Two instances is the smallest change that gives independent main/additional connections. Backward compatibility: the existing `/api/model/config` maps to the MAIN slot so spec-005/018 tests (`test_no_paid_api.py`) stay green; the ADDITIONAL slot is a parallel surface.

**Alternatives considered**: one config object with nested main/additional dicts (rejected — more churn, breaks the existing single-slot API/tests).

## Decision 5: Report path validation mirrors the project-path rule

**Decision**: `audit_path` must be an existing, readable file OUTSIDE the agent repo (same external-only guard `SessionManager.start` already applies to `project_path`). Missing/unreadable/in-repo → clear `ValueError`, no broken session.

**Rationale**: FR-004 + the existing `feedback_no_target_code_in_agent` invariant. Reuses the `_AGENT_ROOT` containment check already in `start()`.

## Injection budget

The report share of context is bounded (e.g. a `REPORT_BUDGET_CHARS` cap, truncated with an explicit `…[report truncated]…` marker) so a large report can't crowd out session facts. Exact value tunable; the existing `build_messages` priority already drops lowest-priority content first.
