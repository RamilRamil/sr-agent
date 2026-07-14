# Feature Specification: Optional Gemini Model Provider

**Feature Branch**: `018-gemini-provider`

**Created**: 2026-07-14

**Status**: Draft

**Input**: User description: "Optional Gemini LLM provider — a paid, isolated, explicitly-selected model backend for the operator frontend."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a session on a hosted Gemini model chosen from the UI (Priority: P1)

The operator opens the frontend, goes to settings, provides a Gemini API key (or relies on one already set in the environment), explicitly selects the Gemini provider, picks a model from a dropdown of Gemini's simpler/cheaper models, and runs a session — the agent's turns are now served by the chosen hosted model instead of the local one. This is valuable when the local model box is unavailable or when a fast, cheap hosted model is preferable for a quick task.

**Why this priority**: This is the whole point of the feature — a working, operator-selected hosted-model path. Everything else supports it.

**Independent Test**: With a Gemini key configured, select the Gemini provider and a model in the UI, start a session, and confirm the turn is produced by the selected hosted model; switching back to local restores local-model behavior.

**Acceptance Scenarios**:

1. **Given** a Gemini key is available and the provider is explicitly selected with a chosen model, **When** the operator runs a session turn, **Then** the turn is served by that hosted model and its output is treated as untrusted model output (never elevated to a human-authored input).
2. **Given** the operator has not selected the Gemini provider, **When** a session runs, **Then** it uses the local model as before — the hosted provider is never used implicitly.
3. **Given** the operator changes the selected model in settings, **When** the next turn runs, **Then** it uses the newly selected model.

---

### User Story 2 - Provide the API key by environment OR by a UI field, UI wins (Priority: P1)

The operator can supply the Gemini API key two ways: through an environment file/variable set at deploy time, or through a dedicated write-only field in the frontend. If both are present, the key entered in the UI takes precedence for that running process. The key is never shown back, never written to disk, and never appears in logs.

**Why this priority**: Key configuration is a precondition for US1 and carries the security-sensitive handling; it must be correct and safe from the start.

**Independent Test**: Set only the env key → provider is usable. Set the UI key on top → the UI key is the one used. Query any status/config surface → it reports only whether a key is present, never the key value.

**Acceptance Scenarios**:

1. **Given** only an environment key is set, **When** the operator selects the Gemini provider, **Then** it works using the environment key.
2. **Given** both an environment key and a UI key are set, **When** a turn runs, **Then** the UI key is used (per-process override).
3. **Given** a key has been set by either means, **When** the operator reads the model-config or any status endpoint, **Then** the response indicates a key is present but never returns the key value; the key never appears in any persisted file or log line.
4. **Given** neither key is set, **When** the operator selects the Gemini provider, **Then** the system reports a clear "no key configured" state and does not attempt a call.

---

### User Story 3 - Keep the hosted provider optional and non-breaking (Priority: P1)

A maintainer must be able to run and test the entire core agent with the hosted-provider software component absent and no Gemini key set — nothing about the core loop may depend on the paid provider. The provider is an explicit, opt-in convenience; its absence degrades gracefully with a clear message, never a crash or a hidden fallback.

**Why this priority**: This is the constitutional guarantee (no paid dependency in the core path). A regression here would make the core loop hostage to a paid service — as serious as the feature itself.

**Independent Test**: With the provider software component uninstalled and no key set, the full test suite passes and the agent runs on the local/relay path; selecting the Gemini provider then yields a clear, actionable "provider unavailable — install/configure it" message rather than an error.

**Acceptance Scenarios**:

1. **Given** the hosted-provider software component is not installed and no key is set, **When** the full suite runs offline, **Then** every existing and core test passes.
2. **Given** the operator selects the Gemini provider while its software component is missing, **When** the selection is applied, **Then** the system returns a clear, actionable message and the local/relay path remains available.
3. **Given** any configuration, **When** the core loop runs without the operator selecting Gemini, **Then** it never invokes the hosted provider.

---

### Edge Cases

- Operator selects Gemini with no key configured → explicit "no key configured" state; no call attempted (not a silent fall-through to local).
- Operator provides an invalid/expired key → the failed turn surfaces the provider's error clearly; the operator can correct the key without restarting the session.
- The hosted-provider software component is absent → selecting it yields an actionable install/configure message; local/relay stays usable.
- Operator clears the UI key while an env key exists → the process falls back to the env key.
- Operator selects a model no longer offered → the system reports an invalid-selection state and keeps the previous working selection or prompts a re-pick.
- Any status/config read → must never echo the key.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST offer Gemini as an explicitly selectable model provider for a session, alongside the existing local-model path.
- **FR-002**: The system MUST accept a Gemini API key from the environment and from a dedicated write-only UI field; when both are present, the UI-provided key MUST take precedence for the running process.
- **FR-003**: The Gemini API key MUST NEVER be returned by any API response, persisted to disk, or written to any log; status surfaces MUST expose only whether a key is present.
- **FR-004**: Selecting the Gemini provider MUST be an explicit operator action; the system MUST NOT route to the hosted provider as an implicit or silent fallback from the local model.
- **FR-005**: The system MUST present a list of selectable Gemini models (favoring the simpler/cheaper tier) that the operator can choose from, and MUST use the chosen model for subsequent turns.
- **FR-006**: Output produced by the Gemini provider MUST carry the same untrusted "external model output" trust status as other model/relay output and MUST NEVER be elevated to a human-authored input.
- **FR-007**: The hosted-provider software component MUST be optional; the core agent MUST import, run, and pass its full test suite with that component absent and no Gemini key set.
- **FR-008**: When the operator selects Gemini while the software component is missing or no key is configured, the system MUST return a clear, actionable message and MUST keep the local/relay path available (no crash, no hidden fallback).
- **FR-009**: The Gemini provider MUST NOT introduce any new privileged or irreversible action and MUST NOT alter the human-confirmation gate or the trust-hierarchy ordering.
- **FR-010**: A configuration change (key, provider, or model) MUST take effect for subsequent turns without requiring a restart.
- **FR-011**: The behavior above MUST be validated by offline, deterministic tests that use no real key and no network (key precedence, key-never-exposed, explicit-selection build path, external-output trust status, graceful absence).
- **FR-012**: Documentation MUST record the provider, the environment-vs-UI key precedence, the model-list selection, and the optional/explicit/graceful (no-paid-dependency) posture.

### Key Entities *(include if feature involves data)*

- **Model Provider Selection**: The operator's current choice of where turns are served (local model vs Gemini), an explicit per-process setting.
- **Gemini Credential**: A write-only secret supplied by environment or UI, with UI-over-environment precedence; represented externally only as "present / absent".
- **Selectable Model**: An entry in the offered list of Gemini models the operator can pick; the current pick drives subsequent turns.
- **Provider Output**: A model turn's result, always tagged as untrusted external model output in the trust hierarchy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can, entirely from the UI, configure a key, select Gemini, pick a model, and run a session turn served by that hosted model — with no code change or restart.
- **SC-002**: In 100% of configurations, the API key is never present in any API response body, persisted file, or log line (only a present/absent indicator is ever exposed).
- **SC-003**: With the hosted-provider software component absent and no key set, the full test suite passes offline and the agent runs on the local/relay path (zero regressions).
- **SC-004**: The hosted provider is used only when explicitly selected — never as an implicit fallback — verifiable across the defined test cases.
- **SC-005**: Key-precedence behavior (UI over environment, environment fallback, neither → clear disabled state) is correct in 100% of the defined offline test cases.

## Assumptions

- The operator surface is single-operator and per-process (consistent with the existing model-config surface); a UI-set key lives only in that process's memory.
- The offered model list favors Gemini's simpler/cheaper tier; the exact catalog is a small, maintainable list resolved at planning time and may be refreshed without a spec change.
- The audit's security-critical stages continue to run on their existing model routing; this feature only adds an operator-selectable session backend and does not re-route those stages.
- "External model output" trust handling already exists for the Claude/relay path; the Gemini provider reuses that same status rather than defining a new one.
- The hosted-provider software component is installed by whoever wants to use Gemini; its absence is a normal, supported state.

## Out of Scope

- Making Gemini the default or any kind of fallback for the core loop or for the security-critical audit stages (extended-thinking Stage 1/3 stay on their existing routing).
- Persisting or syncing the API key anywhere (no storage, no cross-process sharing).
- Token-cost/usage accounting or streaming-output UI.
- Supporting other hosted providers (OpenAI, etc.) — separate future work.
- Any change to the local-model or relay paths, the trust-hierarchy ordering, or the human-confirmation gate.
