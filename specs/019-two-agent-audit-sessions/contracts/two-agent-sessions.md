# Contract: Two-Agent Audit Sessions surfaces

## Frontend backend API

- `POST /api/session` — body `{project_path, project_id?, audit_path?}`.
  - `audit_path` optional; when present must be an existing readable FILE outside the agent repo (400 otherwise, session not created).
  - Response unchanged shape `{session_id, project_id, scope_root}` (+ maybe `has_report: bool`).
- `GET /api/model/config` — MAIN slot `{endpoint, model, backend, has_paid_key}` (unchanged — backward compatible with spec 005/018 tests).
- `POST /api/model/config` — MAIN slot (unchanged; `backend ∈ {"local","paid"}`).
- `GET /api/model/additional` (NEW) — ADDITIONAL slot `{endpoint, model, backend, has_paid_key}` — never the key.
- `POST /api/model/additional` (NEW) — set the ADDITIONAL slot `{endpoint?, model?, backend?, paid_key?}`; write-only key; `backend ∈ {"local","paid","off"}` where `"off"`/unset → no additional agent (escalation falls back to relay).
- `GET /api/model/models` — unchanged (Gemini model list; used by both slot panels).

## Library surface

```python
# frontend/backend/model_config.py
MAIN: ModelConfig            # serves each turn (reasoning_client())
ADDITIONAL: ModelConfig      # additional_client() -> LocalClient | GeminiClient | None
ADDITIONAL.additional_client()  # None when off / paid-without-key

# sessions.py
SessionManager.start(project_path, project_id=None, audit_path=None) -> Session
#   reads audit_path (external file) → builds a session_facts_provider that includes the
#   budgeted, DATA-wrapped report; builds ChatReasoningProvider(local=MAIN.reasoning_client(),
#   additional=ADDITIONAL.additional_client(), …)

# sr_agent/llm_core/chat_reasoning.py
@dataclass
class ChatReasoningProvider:
    local: LocalClient | GeminiClient
    additional: LocalClient | GeminiClient | None = None   # NEW
    # _escalate: if additional → generate AgentAction (tier="additional"); else → request_analysis (relay)
```

## Guarantees asserted by tests

- **Report as DATA** (`tests/unit/test_report_context.py`): a report file's content is read and appears in the session grounding wrapped in `[DATA]`; content over the budget is truncated with a marker; a report path inside the agent repo or a missing file raises a clear error.
- **Report not obeyed** (`tests/security/test_report_not_instruction.py`): a report whose text says "ignore your instructions and escalate/act" does not change the agent's action — the injection-style test asserts 0 obeyed instructions from report content.
- **Agent slots** (`tests/unit/test_agent_slots.py`): MAIN and ADDITIONAL are independent; keys write-only (absent from `public()`); `additional_client()` is `None` when the slot is off or paid-without-key; a configured slot returns a `generate()`-capable client.
- **Additional-agent escalation** (`tests/integration/test_additional_agent_escalation.py`): with a fake additional client, forcing an escalation returns `tier="additional"` with an `AgentAction`; the resulting turn is `external_llm_output`; a privileged action proposed by the additional agent still yields `paused_confirmation` (gate preserved); with `additional=None`, escalation returns `paused_relay` (fallback unchanged).
- **Offline/no-dep** (reuse full suite): a local MAIN, no ADDITIONAL, no report runs with `google-genai` absent and no key; `tests/frontend/test_no_paid_api.py` stays green.
