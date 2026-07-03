# Feature Specification: Operator Frontend

**Feature Branch**: `005-operator-frontend`

**Created**: 2026-07-02

**Status**: Draft

**Input**: User description: "A single-operator containerized web UI to run, observe, and control sr-agent solo — chat, live reasoning, trust/provenance + OOB confirmation queue, memory browser, health & architecture introspection; a thin view over kernel state, never a shortcut around the confirmation gate."

## Context & Motivation

The operator will often work with sr-agent **alone**, without pairing with a coding assistant. Today the only surface is the CLI. A frontend gives a solo operator one place to: drive a session bound to a target codebase; see what the agent is doing and thinking *right now* and what it did *while they were away*; approve or reject the privileged actions it proposes — safely; and understand the agent's architecture, connected modules, and health.

Crucially, this is a **thin view over state the kernel already produces** (session facts, the findings roadmap, the consequential-action notice, the routing/tier decision, readiness, the HMAC episodic memory) plus a **properly-gated action surface** — not a new decision or execution path. It is, in effect, another operator surface subject to exactly the same guarantees as the CLI. Its one distinctive risk is that a convenient GUI could tempt a shortcut around the human-authority confirmation gate; the spec forbids that outright.

## User Scenarios & Testing *(mandatory)*

The actor is a single local operator. Stories are prioritized: US1+US2 are the usable-and-safe core; US3+US4 add after-the-fact and trust observability; US5 adds introspection.

### User Story 1 - Run and observe a session (Priority: P1)

As the operator, I open the UI, start (or resume) a session bound to a target project folder, send messages, and watch the agent work — its answers plus a live view of what it is doing this turn (the action it intends, the routing tier, the tool-call budget it has used) — without touching the CLI.

**Why this priority**: This is the MVP — the core "operate the agent solo" loop. Without it there is no frontend; with just it, an operator already has a usable window into the agent.

**Independent Test**: Start a session against a folder, send a question, and confirm the reply appears alongside a live trace of the turn's steps; reload and resume the same session.

**Acceptance Scenarios**:

1. **Given** the UI is open, **When** the operator points it at a target folder and starts a session, **Then** a session is created bound to that project and the agent's first reply appears without any CLI use.
2. **Given** an active turn, **When** the agent selects and runs tools, **Then** the operator sees the intended next action, its parameters, the reasoning summary, and the tool-call budget used vs. the limit, updating in near-real-time.
3. **Given** a slow local-model turn, **When** the agent is generating, **Then** the UI visibly indicates progress/liveness (not a frozen screen).
4. **Given** a prior session, **When** the operator resumes it, **Then** the working scope and grounding are restored.

---

### User Story 2 - Approve or reject privileged actions, safely (Priority: P1)

As the operator, when the agent proposes a privileged or irreversible action (e.g. writing/running a PoC, a privileged status change), I see it in a confirmation queue with a clear notice of exactly what will run, and I approve or reject it as a deliberate act — the UI never lets such an action run without my explicit decision, and never turns approval into a reflexive one-click.

**Why this priority**: Co-MVP. The agent's write/execute path is central to its work, and preserving the out-of-band human-authority gate in this new surface is non-negotiable (Constitution II). A frontend that weakens the gate is worse than no frontend.

**Independent Test**: Drive the agent to propose a write/execute action; confirm it appears in the queue with its consequential-action notice, does not execute until explicitly approved, and that approval requires a deliberate action rather than incidental navigation.

**Acceptance Scenarios**:

1. **Given** the agent proposes a write/execute or privileged-status action, **When** the turn reaches the gate, **Then** the action appears in the confirmation queue with a notice describing exactly what would run, and does not execute.
2. **Given** a pending confirmation, **When** the operator explicitly approves it, **Then** the action proceeds; **When** they reject it or leave it pending, **Then** it never executes (fail-safe).
3. **Given** a pending confirmation, **When** the operator merely navigates the UI, **Then** nothing is approved by accident — approval is a distinct, deliberate act, not equivalent to ordinary clicks.

---

### User Story 3 - Reconstruct what happened while away (Priority: P2)

As an operator returning after being away, I can reconstruct everything the agent did in my absence from an append-only audit trail plus a read-only memory browser — every action taken, every confirmation decided, every tool run, and every finding/checkpoint/status recorded.

**Why this priority**: Solo operation means the operator is often not watching live; the ability to review after the fact is what makes unattended stretches safe and useful. Valuable but not required for the first usable loop.

**Independent Test**: Run the agent through several actions and confirmations, then, from a fresh view, reconstruct the sequence of what it did purely from the audit trail and memory browser.

**Acceptance Scenarios**:

1. **Given** the agent has acted over a session, **When** the operator opens the audit trail, **Then** each action, confirmation decision, and tool run is listed in order.
2. **Given** recorded memory, **When** the operator opens the memory browser for the project, **Then** findings, checkpoints, and status events are viewable read-only, with no ability to edit or delete.

---

### User Story 4 - See the trust boundary (Priority: P2)

As the operator, I can see the agent's trust boundary made legible: every context block is tagged with its source trust tier, untrusted DATA-wrapped content is visually distinct, and when a turn escalates I can see which deterministic trigger fired and why.

**Why this priority**: This is the project's signature — making the security model visible for trust, learning, and demos. It rides on the same session view but is not required for the core loop.

**Independent Test**: Feed the agent a turn that includes tool output containing instruction-like text; confirm that content is displayed as tagged untrusted DATA, not as trusted instruction, and that any triggered escalation is shown with its reason.

**Acceptance Scenarios**:

1. **Given** a turn's context, **When** it is displayed, **Then** each block shows its trust tier and DATA-wrapped external content is visually distinguishable from trusted orchestrator content.
2. **Given** an escalation occurs, **When** the operator inspects the turn, **Then** the triggering condition and its reason are shown.
3. **Given** untrusted content that mimics UI controls or instructions, **When** it is displayed, **Then** it renders as inert data and cannot act as a control or be mistaken for trusted UI.

---

### User Story 5 - Understand the agent's makeup and health (Priority: P3)

As the operator, I can see whether the agent is ready to work, which modules and pack are active with the pack's tools, and a reference to the agent's architecture and command help — so I can orient, diagnose, and demonstrate without reading logs.

**Why this priority**: Orientation and diagnosis aids; high value for understanding and demos, but the agent is operable without them.

**Independent Test**: With the model down and then up, confirm the health view reflects readiness correctly; confirm the active pack and its tools are listed; open the architecture/help reference.

**Acceptance Scenarios**:

1. **Given** the local model is not ready, **When** the operator opens the health view, **Then** it shows the agent as not ready (not merely "reachable") and does not present the agent as able to work.
2. **Given** an active pack, **When** the operator opens the modules view, **Then** the kernel and the active pack are shown with the pack's registered tools.
3. **Given** the UI is open, **When** the operator opens help, **Then** an architecture reference (kernel/pack + invariants) and a command reference are available.

### Edge Cases

- **Local model unavailable**: the UI shows a blocked/unavailable state and does not fabricate progress (mirrors the agent's refuse-and-wait behavior); it does not silently fall back to a paid path.
- **Confirmation left pending while away**: the action stays queued and does NOT execute (fail-safe), and is visible on return.
- **Reconnect mid-turn**: reopening/reloading the UI reattaches to the running session and shows current state rather than losing it.
- **Untrusted content mimicking UI**: DATA-wrapped content that looks like controls or instructions renders inert and cannot act as a control or masquerade as trusted UI (a display-layer injection guard).
- **Pack with no domain panels**: the generic panels still function; the UI does not break when a pack contributes no views.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The UI MUST let the operator start a session bound to a specified target project/folder, and resume an existing session, reusing the agent's project-binding and resumability.
- **FR-002**: The UI MUST let the operator send messages to the agent and display its replies within the bound session.
- **FR-003**: The UI MUST display the active session's working scope — the scope root and the files the agent has read this session.
- **FR-004**: The UI MUST show, in near-real-time, the agent's current step: the intended next action and its parameters, the reasoning summary, and the per-turn tool-call budget used vs. the limit.
- **FR-005**: The UI MUST show each turn's routing tier (local vs relay) and, when a turn escalates, which deterministic trigger fired and why.
- **FR-006**: The UI MUST indicate liveness during generation so a slow local-model turn is visibly working rather than appearing hung.
- **FR-007**: The UI MUST tag every displayed context block with its source trust tier and visibly mark DATA-wrapped (external/untrusted) content, so the trust boundary is legible.
- **FR-008**: The UI MUST present a confirmation queue of pending privileged/irreversible actions, each with a notice describing exactly what would run, and let the operator approve or reject each.
- **FR-009**: Approving a privileged/irreversible action through the UI MUST remain a deliberate, explicit act and MUST NOT bypass, disable, or weaken the out-of-band confirmation gate. The UI MUST NOT auto-approve, and MUST NOT make approval a reflexive action equivalent to ordinary navigation.
- **FR-010**: The UI MUST provide a read-only browser of the HMAC episodic memory for the bound project (findings, checkpoints, status events); it MUST NOT allow editing or deleting memory.
- **FR-011**: The UI MUST show system health — model readiness (ready vs merely reachable), the active model, sandbox availability, and local-model reachability.
- **FR-012**: The UI MUST show the connected modules — the kernel and the active capability pack, including the pack's registered tools.
- **FR-013**: The UI MUST provide an append-only audit trail of actions taken, confirmation decisions, and tool runs, reviewable after the fact.
- **FR-014**: The UI MUST provide an agent-architecture reference (kernel/pack structure + security invariants) and a command/help reference.
- **FR-015**: The UI MUST be a surface over existing agent state and MUST NOT embed decision logic, introduce new agent capabilities, or weaken any kernel invariant — it is subject to the same guarantees as the CLI.
- **FR-016**: The UI MUST function against the local model / relay only and MUST NOT require a paid API for any surface.
- **FR-017**: Domain-specific panels (findings roadmap, PoC status, graph/SIG views) MUST be contributed by the active pack rather than hardcoded; the generic panels (chat, live trace, confirmation queue, memory browser, health, modules) MUST work for any pack.
- **FR-018**: The UI MUST run locally in a container alongside the existing services, for a single operator — no multi-user, accounts, authentication, or remote/public hosting.

### Key Entities

- **Operator Session View**: the bound project, conversation, and working scope for one session.
- **Reasoning/Trace Event**: a step in the current turn — intended action, params, reasoning summary, tier, budget usage.
- **Confirmation Item**: a pending privileged/irreversible action with its consequential-action notice and decision state (pending/approved/rejected).
- **Provenance-Tagged Block**: a unit of displayed context carrying its source trust tier and DATA-wrapping state.
- **Memory Record View**: a read-only rendering of an HMAC episodic record (finding/checkpoint/status).
- **Health Status**: model readiness, active model, sandbox and local-model reachability.
- **Module/Pack Descriptor**: the active kernel + pack and the pack's tools.
- **Audit-Trail Entry**: an append-only record of an action taken, a confirmation decided, or a tool run.
- **Pack-Contributed Panel**: a domain view supplied by the active pack.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can start or resume a session bound to a target folder and get the agent's first answer entirely from the UI, with no CLI use.
- **SC-002**: While the agent works a turn, the operator can see its current intended action, tier, and budget within a few seconds of it happening, and can tell a slow turn is alive vs. hung.
- **SC-003**: 100% of pending privileged/irreversible actions appear in the confirmation queue with a description of what would run, and none can execute without a deliberate operator approval (no auto-approve; approval is not a reflexive navigation-equivalent click).
- **SC-004**: In 100% of displayed context, each block shows its trust tier and untrusted DATA-wrapped content is visually distinguishable from trusted content.
- **SC-005**: A returning operator can reconstruct the full sequence of what the agent did in their absence from the audit trail and memory browser alone.
- **SC-006**: The operator can determine from the UI whether the agent is ready to work (model ready, sandbox up) and which pack/tools are active, without reading logs.
- **SC-007**: Every UI surface functions with the local model only — zero dependency on a paid API.
- **SC-008**: Changing the active pack changes the domain panels while the generic panels continue to work unchanged.

## Assumptions

- **Single local operator.** No authentication, multi-user, remote/public hosting, or mobile — explicitly out of scope.
- **Thin view over kernel state.** The UI renders state the kernel/pack already expose; where a needed piece of state is not yet exposed, a thin read-only accessor may be added, but no decision logic moves into the UI.
- **Approval mechanism.** The UI may host the approval of a pending action, but approval must remain a deliberate, friction-ful, explicit act (e.g. an explicit review-and-confirm step), never a reflexive one-click; whether approval stays a fully separate channel (as `sr-agent confirm`) or a gated in-UI step is a plan-phase design detail, bounded by FR-009.
- **"Near-real-time"** means within a few seconds — adequate for a human operator watching a slow local model, not a hard latency SLA.
- **Containerized, local.** The UI is served from a container alongside the existing Ollama/sandbox services and accessed locally in a browser.
- **No new agent capability.** The frontend surfaces and gates only what the agent already does; adding agent abilities is out of scope.
- The specific UI framework/toolkit is an implementation detail for the plan phase, not this spec.

## Dependencies

- Builds on features 001 (secure kernel: trust tiers, HMAC memory, confirmation gate, escalation), 003 (chat session: project binding, resumability, routing tier, per-turn budget, consequential-action notice, findings roadmap), and is consistent with feature 004's kernel/pack seam (generic panels = kernel; domain panels = pack-contributed).
- Governed by Constitution v1.0.0 — especially Principle II (human authority / the gate must not be shortcut), Principle III (kernel/pack separation for panels), and Principle V (no paid-API dependency).
