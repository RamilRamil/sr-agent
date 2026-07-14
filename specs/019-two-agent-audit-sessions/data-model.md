# Data Model: Two-Agent Audit Sessions (spec 019)

No persistent storage. Entities are in-memory config/session objects.

## Entity: Agent Slot (`ModelConfig`, reused from spec 018 — two instances)

| Field | Notes |
|-------|-------|
| `endpoint` | local endpoint (Ollama URL) for method=local |
| `model` | model name (local model or Gemini model id) |
| `backend` | `"local" \| "paid"` — connection method (`"paid"` = hosted/Gemini) |
| `_paid_key` | write-only hosted key; UI-over-env; never in `public()`/logs/disk |

Two process-wide instances:
- **`MAIN`** — serves every non-escalated turn. `reasoning_client()` (existing) → `LocalClient` or `GeminiClient`.
- **`ADDITIONAL`** — consulted on escalation. New `additional_client() -> LocalClient | GeminiClient | None`:
  - `None` when unconfigured — method local with unreachable endpoint is still a client, but "unconfigured" = backend paid with no key, or an explicit "off" state → returns `None` so `_escalate` falls back to relay.
  - Otherwise a `generate()`-duck client (local or Gemini).

`public()` per slot: `{endpoint, model, backend, has_paid_key}` — never the key.

## Entity: Session Inputs (edited `SessionManager.start`)

| Field | Change |
|-------|--------|
| `project_path` | unchanged (required, external dir) |
| `audit_path` | NEW — optional path to an external report FILE; validated: exists, readable, outside the agent repo |

## Entity: Audit Report Context

- Read from `audit_path` at session start; held in memory for the session.
- Injected via the `session_facts_provider` the frontend supplies to `OrchestratorLoop`, so `build_messages` wraps it as `wrap_data(tool="session_facts"/"audit_report", …)` — untrusted `[DATA]`.
- Bounded by `REPORT_BUDGET_CHARS`; overflow truncated with an explicit marker.

## Entity: Escalation Consultation (edited `ChatReasoningProvider`)

New optional field on the provider:

| Field | Notes |
|-------|-------|
| `additional` | `LocalClient \| GeminiClient \| None` — the additional-agent client (from `ADDITIONAL.additional_client()`) |

`_escalate(messages, trigger, source)` behavior:
- If `self.additional is not None`: `raw = self.additional.generate(self._render(messages), fmt="json")`; `action = self._parse(raw)`; return `ReasoningOutcome(kind="action", agent_action=action, tier="additional", escalation_trigger=trigger, escalation_source=source)`.
- Else (unchanged): `request_analysis(...)` → `ReasoningOutcome(kind="paused_relay", …)`.

## Trust / gate relationships (unchanged, inherited)

- Report + additional-agent output → `ChatTurn.source_type = external_llm_output` (structural; never `human_input`).
- An additional-agent `AgentAction` re-enters `run_turn` → any privileged/irreversible action still hits `request_confirmation` (the human gate). The additional agent cannot self-authorize.
- `SourceType` ordering, the confirmation gate, and Stage 2's `request_analysis` use are NOT modified.
