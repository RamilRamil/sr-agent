# Feature Specification: OpenRouter Provider with GLM as a Selectable Model

**Feature Branch**: `020-openrouter-glm-provider`

**Created**: 2026-07-14

**Status**: Draft

**Input**: User description: "Add OpenRouter as a main-model connection (GLM 5.2), keyed from the environment; select it from a dropdown."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a session on GLM via OpenRouter, selected from a dropdown (Priority: P1)

The operator has set an OpenRouter API key in the environment (a `.env` file). In the frontend they open settings, choose "OpenRouter" as the connection for the main agent, pick the GLM model from the model dropdown, and run a session — turns are now served by GLM through OpenRouter. No key is typed into the browser; the key comes from the environment.

**Why this priority**: This is the whole feature — an operator-selected, env-keyed hosted model (GLM) added to the existing choices. Everything else supports it.

**Independent Test**: With an OpenRouter key in the environment, select OpenRouter + the GLM model and run a turn; the turn is produced by that hosted model, and its output is treated as untrusted model output. Switching back to the local model restores local behavior.

**Acceptance Scenarios**:

1. **Given** an OpenRouter key is set in the environment and the main agent is explicitly set to OpenRouter with the GLM model, **When** a turn runs, **Then** it is served by GLM via OpenRouter and its output is untrusted model output (never elevated to an operator-authored input).
2. **Given** the operator has not selected OpenRouter, **When** a session runs, **Then** it uses the local model as before — OpenRouter is never used implicitly.
3. **Given** the operator picks a different model from the OpenRouter list, **When** the next turn runs, **Then** it uses the newly selected model.

---

### User Story 2 - Key comes from the environment; disabled without one (Priority: P1)

The OpenRouter key is read from the environment. If an operator does supply a key through the optional write-only UI field, that overrides the environment for the running process. The key is never shown back, written to disk, or logged. With no key configured at all, OpenRouter is a clear disabled state — selecting it does not attempt a call.

**Why this priority**: Key handling is the security-sensitive precondition; it must be correct and safe from the start, and the env-first path is the operator's chosen default.

**Independent Test**: Set only the environment key → OpenRouter is usable. Provide a UI key on top → the UI key is used. Read any status/config surface → it reports only whether a key is present, never the value. With neither → selecting OpenRouter reports a clear "no key configured" state.

**Acceptance Scenarios**:

1. **Given** only an environment key is set, **When** the operator selects OpenRouter, **Then** it works using the environment key.
2. **Given** both an environment key and a UI key are set, **When** a turn runs, **Then** the UI key is used (per-process override).
3. **Given** a key is present by either means, **When** the operator reads the config/status, **Then** the response indicates a key is present but never returns the key; the key appears in no persisted file or log.
4. **Given** no key is configured, **When** the operator selects OpenRouter, **Then** the system reports a clear disabled state and does not attempt a call.

---

### User Story 3 - Keep OpenRouter optional and non-breaking (Priority: P1)

A maintainer must be able to run and test the whole core agent with no OpenRouter key and no OpenRouter usage — nothing about the core loop may depend on this paid provider, and no new software package is introduced for it. OpenRouter is an explicit, opt-in convenience.

**Why this priority**: This is the constitutional guarantee (no paid dependency in the core path). A regression here would tie the core loop to a paid service.

**Independent Test**: With no OpenRouter key set and OpenRouter unused, the full test suite passes offline and the agent runs on the local/relay path; selecting OpenRouter with no key yields a clear disabled state rather than an error.

**Acceptance Scenarios**:

1. **Given** no OpenRouter key and no OpenRouter usage, **When** the full suite runs offline, **Then** every existing and core test passes and no new software package is required.
2. **Given** the operator selects OpenRouter with no key, **When** the selection is applied, **Then** the system returns a clear disabled state and the local/relay path remains available.
3. **Given** any configuration, **When** the core loop runs without the operator selecting OpenRouter, **Then** it never contacts OpenRouter.

---

### Edge Cases

- Operator selects OpenRouter with no key (env or UI) → explicit "no key configured" disabled state; no call attempted (not a silent fall-through to local).
- Invalid/expired key or an OpenRouter error → the failed turn surfaces the error clearly; the operator can fix the key without restarting the session.
- Selected GLM model slug not available on OpenRouter → the failed turn surfaces the provider's error; the operator can pick another model.
- Any config/status read → never echoes the key.
- Operator provides a model slug not in the curated list → allowed (typed value used); the dropdown just favors the GLM option.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST offer OpenRouter as an explicitly selectable connection method for the main agent (and, consistently, the additional agent), alongside the existing local and Gemini options.
- **FR-002**: The system MUST present a curated list of selectable OpenRouter models with the GLM option first, and MUST use the chosen model for subsequent turns.
- **FR-003**: The OpenRouter API key MUST be read from the environment; a write-only UI key, if provided, MUST override the environment for the running process.
- **FR-004**: The OpenRouter API key MUST NEVER be returned by any response, persisted to disk, or written to a log; status surfaces MUST expose only whether a key is present.
- **FR-005**: Selecting OpenRouter MUST be an explicit operator action; the system MUST NOT route to OpenRouter as an implicit or silent fallback from another model.
- **FR-006**: Output produced via OpenRouter MUST carry the untrusted "external model output" trust status and MUST NEVER be elevated to an operator-authored input.
- **FR-007**: Adding OpenRouter MUST NOT introduce any new software package/dependency.
- **FR-008**: OpenRouter MUST be optional; the core agent MUST run and its full test suite MUST pass with no OpenRouter key set and OpenRouter unused.
- **FR-009**: When the operator selects OpenRouter with no key configured, the system MUST return a clear disabled state and keep the local/relay path available (no crash, no hidden fallback).
- **FR-010**: OpenRouter MUST NOT introduce any new privileged or irreversible action and MUST NOT alter the human-confirmation gate or the trust-hierarchy ordering.
- **FR-011**: A configuration change (selecting OpenRouter, or the chosen model) MUST take effect for subsequent turns without a restart.
- **FR-012**: The behavior above MUST be validated by offline, deterministic tests using no real key and no network (the provider call is simulated): model-selection, key precedence, key-never-exposed, external-output trust status, disabled-state with no key.
- **FR-013**: Documentation MUST record the provider, the environment-keyed path, the GLM model selection, and the optional/explicit/graceful (no-paid-dependency, no-new-package) posture.

### Key Entities *(include if feature involves data)*

- **Connection Method**: How an agent slot connects — now including OpenRouter, alongside local and Gemini; an explicit per-process choice.
- **OpenRouter Credential**: A write-only secret sourced from the environment (or an optional UI override); represented externally only as "present / absent".
- **Selectable Model**: An entry in the offered OpenRouter model list (GLM first) the operator picks; the current pick drives subsequent turns.
- **Provider Output**: A model turn's result via OpenRouter, always tagged as untrusted external model output.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With an OpenRouter key in the environment, the operator can, from the UI, select OpenRouter + GLM and run a session turn served by that model — no restart, no key typed into the browser.
- **SC-002**: In 100% of configurations, the API key never appears in any API response, persisted file, or log — only a present/absent indicator.
- **SC-003**: With no OpenRouter key and OpenRouter unused, the full test suite passes offline and no new software package is required (zero regressions).
- **SC-004**: OpenRouter is used only when explicitly selected — never as an implicit fallback — verifiable across the defined test cases.
- **SC-005**: Key-precedence behavior (UI over environment, environment fallback, neither → clear disabled state) is correct in 100% of the defined offline test cases.

## Assumptions

- Single-operator, process-wide configuration (consistent with the existing agent-slot surface); a UI-set key lives only in that process's memory, and the environment key is the documented default.
- The offered model list favors the GLM option; the exact model catalog (and the GLM slug) is resolved at planning time from the provider's current model listing and may be refreshed without a spec change.
- "External model output" trust handling and the human-confirmation gate already exist and are reused as-is; this feature defines no new trust tier or gate.
- OpenRouter is reached over the provider's standard interface with the key; this feature adds the provider as one more selectable method, not a general multi-provider abstraction.
- The security-critical audit stages keep their existing routing; this feature only adds an operator-selectable session backend.

## Out of Scope

- Making OpenRouter/GLM the default or any kind of fallback for the core loop or the security-critical audit stages.
- Adding any new software package/dependency for OpenRouter.
- A general multi-provider abstraction beyond adding this one connection method.
- Supporting arbitrary provider models beyond the curated list in the dropdown (a slug can still be typed, but the list favors GLM).
- Persisting or syncing the API key anywhere.
- Any change to the local/Gemini/relay paths, the trust-hierarchy ordering, or the human-confirmation gate.
