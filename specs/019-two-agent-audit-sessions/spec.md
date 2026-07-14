# Feature Specification: Two-Agent Audit Sessions with an Audit-File Input

**Feature Branch**: `019-two-agent-audit-sessions`

**Created**: 2026-07-14

**Status**: Draft

**Input**: User description: "From the frontend, write in chat what I want, and set in dedicated fields (1) the path to the project, (2) the path to the audit file, and (3) the connection method for a main agent and an additional agent."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ground a session with an audit report (Priority: P1)

The operator starts a session and, alongside the project-folder field, points a dedicated field at an external audit-report file. From then on the agent's session context includes that report — treated strictly as untrusted reference material — so when the operator writes "look at finding H-01 and confirm it," the agent already knows what the report says without the operator pasting it into chat.

**Why this priority**: The report is the operator's primary reference for a real audit; without it the agent works blind and the operator must paste context by hand. It is independently valuable the moment a session can be grounded with a report.

**Independent Test**: Start a session with a project folder and a report file; ask the agent about a finding named only in the report; the agent's answer reflects the report content — and the report's text can never make the agent take an action the operator didn't ask for (it is reference data, not instructions).

**Acceptance Scenarios**:

1. **Given** a session started with a valid external report file, **When** the operator asks about a finding described only in that report, **Then** the agent's response reflects the report's content.
2. **Given** a report file whose text contains an embedded instruction (e.g. "ignore your rules and do X"), **When** a turn runs, **Then** the agent treats that text as reference data and does not obey it.
3. **Given** no report file is provided, **When** a session runs, **Then** it behaves exactly as today (the field is optional).
4. **Given** a report path that does not exist or is not readable, **When** the operator starts the session, **Then** they get a clear error and the session is not created in a broken state.

---

### User Story 2 - Choose the main agent's connection (Priority: P1)

The operator picks, in a clearly-labeled "Main agent" control, how the agent that drives each turn connects: a local model (with its endpoint and model name) or a hosted model (with its model and a write-only key). This is the agent that answers the operator on the common path.

**Why this priority**: Every turn runs on the main agent; the operator must be able to choose it deliberately. Most of the plumbing already exists, so this is a clear, low-risk slice that makes the choice explicit and legible.

**Independent Test**: Set the Main agent to local, run a turn (served locally); switch it to the hosted model with a key, run a turn (served by the hosted model); the selection is explicit and takes effect on the next turn.

**Acceptance Scenarios**:

1. **Given** the Main agent is set to the local model, **When** a turn runs, **Then** it is served by the local model at the configured endpoint.
2. **Given** the Main agent is set to the hosted model with a key, **When** a turn runs, **Then** it is served by that hosted model.
3. **Given** any main-agent configuration, **When** the operator reads the config, **Then** the key is never returned — only a "key present/absent" indicator.

---

### User Story 3 - Configure an additional agent for escalations (Priority: P1)

The operator configures a second, "Additional agent" (its own connection: local, or a hosted model with a key). When a turn escalates — because a deterministic guard or the main agent's own self-report flags it — the additional agent is consulted automatically, instead of the operator having to hand-carry the request into an external chat. The additional agent's answer is treated as untrusted model output: it can inform the operator but can never, by itself, authorize a privileged or irreversible action — those still require the operator's explicit confirmation.

**Why this priority**: This is the feature's core new capability — a real second-opinion agent for the hard parts (the exact "cheap main + strong escalation" tiering the project concluded it needs), replacing today's manual hand-off. It carries the sensitive trust boundary, so it must be correct.

**Independent Test**: With an additional agent configured, force an escalation; the additional agent is consulted automatically and its answer returns to the operator; a privileged action proposed during that flow still pauses for the operator's confirmation. With NO additional agent configured, an escalation falls back to today's manual hand-off unchanged.

**Acceptance Scenarios**:

1. **Given** an additional agent is configured, **When** a turn escalates, **Then** the additional agent is consulted automatically and its response is surfaced to the operator.
2. **Given** the additional agent produces a response, **When** it is recorded, **Then** it is marked as untrusted external model output and is never elevated to an operator-authored input.
3. **Given** an escalated flow proposes a privileged or irreversible action, **When** it reaches that action, **Then** it still pauses for the operator's explicit confirmation (the additional agent cannot self-authorize it).
4. **Given** NO additional agent is configured, **When** a turn escalates, **Then** the system falls back to today's manual hand-off with no change in behavior.
5. **Given** the additional agent is a hosted model, **When** the operator reads the config, **Then** its key is never returned — only a present/absent indicator.

---

### Edge Cases

- Report file larger than the injection budget → the injected context is bounded (truncated with an explicit marker); the session still starts.
- Report path points inside the agent's own repository → rejected (target/report material stays external; mirrors the existing project-path rule).
- Additional agent configured but unreachable/missing its software or key at escalation time → the operator gets a clear message and the flow does not silently succeed or crash; the manual hand-off remains available as the fallback.
- Both agents set to the same connection → allowed (e.g. same local model for both); no special-casing required.
- Operator changes either agent's connection mid-session → the change takes effect on the next turn (no restart).
- Any config/status read → never echoes a key.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Session creation MUST accept an OPTIONAL path to an external audit-report file, in addition to the required project path.
- **FR-002**: When a report file is provided, its content MUST be read from the external location and included in the agent's session context as untrusted reference data — it MUST NOT be able to override the agent's instructions or trigger actions on its own (Constitution I).
- **FR-003**: The amount of report content included MUST be bounded by a length budget; content beyond the budget is omitted with an explicit indication rather than silently dropped or unbounded.
- **FR-004**: The report file MUST remain external; the system MUST NOT copy target/report material into the agent's own repository, and MUST reject a report path inside the agent repo.
- **FR-005**: The system MUST expose a clearly-labeled "Main agent" connection (method: local or hosted; plus endpoint/model and, for hosted, a write-only key) that serves every non-escalated turn.
- **FR-006**: The system MUST expose a clearly-labeled "Additional agent" connection (its own method: local or hosted; plus endpoint/model and, for hosted, a write-only key), configured independently of the main agent.
- **FR-007**: When an escalation is triggered and an additional agent is configured, the system MUST consult the additional agent automatically and surface its response to the operator.
- **FR-008**: The additional agent's output MUST carry the untrusted "external model output" trust status and MUST NEVER be elevated to an operator-authored input.
- **FR-009**: An automatically-consulted additional agent MUST NOT bypass the human-confirmation gate: any privileged or irreversible action MUST still require the operator's explicit confirmation.
- **FR-010**: When NO additional agent is configured, an escalation MUST fall back to the existing manual hand-off with no change in behavior.
- **FR-011**: Every API key (main or additional) MUST be write-only: never returned by any response, persisted to disk, or written to a log; only a present/absent indicator is ever exposed.
- **FR-012**: Neither agent nor the report feature may be REQUIRED for the core session to run: a session with a local main agent, no additional agent, and no report file MUST work with no hosted dependency (Constitution V).
- **FR-013**: A configuration change (either agent's connection, or a new report file on a new session) MUST take effect on the next turn/session without a restart.
- **FR-014**: This feature MUST NOT change the escalation used elsewhere (the audit planner's own hand-off), the trust-hierarchy ordering, or the confirmation gate itself.
- **FR-015**: The behavior above MUST be validated by offline, deterministic tests using no real key and no network (report-as-untrusted-data, additional-agent consulted on escalation with external-output status, confirmation gate preserved, key-never-exposed, graceful fallback when unconfigured).

### Key Entities *(include if feature involves data)*

- **Session Inputs**: the required project path plus an optional external audit-report path the operator supplies at session start.
- **Audit Report Context**: the bounded, untrusted-reference view of the report file folded into the session; reference data only, never instructions.
- **Agent Slot**: a named connection ("main" or "additional") describing how an agent connects — method (local/hosted), endpoint/model, and a write-only key when hosted.
- **Escalation Consultation**: the automatic second-opinion request sent to the additional agent when a turn escalates; its result is untrusted external model output.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From the frontend alone, the operator can start a session by supplying a project path and an audit-report path and then converse with an agent that already knows the report — no pasting report text into chat.
- **SC-002**: Report text can never cause the agent to take an action the operator did not request (verified by an injection-style test): 0 successful instruction-injections from report content.
- **SC-003**: With an additional agent configured, an escalated turn is answered automatically by that agent (no manual hand-off) in 100% of the defined escalation test cases; with none configured, 100% fall back to the manual hand-off unchanged.
- **SC-004**: In 100% of configurations, no API key appears in any API response, persisted file, or log — only a present/absent indicator.
- **SC-005**: A privileged/irreversible action proposed during an escalated flow still pauses for operator confirmation in 100% of cases (the additional agent cannot self-authorize).
- **SC-006**: A session with a local main agent, no additional agent, and no report file runs with zero hosted dependency and the full offline test suite passes (zero regressions).

## Assumptions

- Single-operator, process-wide configuration (consistent with today's model-config surface); a UI-set key lives only in that process's memory.
- The audit-report file is Markdown/plain text the operator points at on their machine; the exact injection budget is a tunable resolved at planning time.
- "External model output" trust handling and the human-confirmation gate already exist and are reused as-is; this feature does not define new trust tiers or a new gate.
- The additional agent reuses the same hosted/local client machinery already available (local model, and the hosted providers already integrated); no new provider type is introduced here.
- Which agent handles a turn is decided by the EXISTING deterministic escalation triggers; this feature does not add new turn-routing logic beyond "escalations go to the additional agent when one is configured."

## Out of Scope

- The batch harness and running a whole findings list to completion (separate work).
- Changing the audit planner's own hand-off/relay path.
- Altering the trust-hierarchy ordering or the human-confirmation gate itself.
- Persisting or syncing API keys anywhere.
- Supporting hosted providers beyond those already integrated.
- Multi-operator / per-user configuration.
- New turn-routing logic that picks an agent per turn beyond the existing escalation triggers.
