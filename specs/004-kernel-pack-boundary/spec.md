# Feature Specification: Kernel / Capability-Pack Boundary

**Feature Branch**: `004-kernel-pack-boundary`

**Created**: 2026-07-02

**Status**: Draft

**Input**: User description: "Draw and document the seam between the task-agnostic secure kernel and the task-specific audit pack; extract audit-specifics behind a documented pack interface; no dynamic plugin registry (YAGNI — one pack exists today)."

## Context & Motivation

SR-agent has a dual goal, in priority order (Constitution): (1) a reusable **memory-injection-resistant secure agent** — the task-agnostic kernel; (2) an **audit agent** that demonstrates it — the first capability pack. Today the two are entangled: the concrete audit action types, the audit tool descriptions, the finding/severity/tag models, the planner methodology, and the audit privileged-status set are woven directly through modules that are supposed to be the reusable core. The deterministic action-validation gate, for example, is a mix of kernel *mechanism* (whitelist check, risk-class annotation, out-of-band confirmation flagging, path-containment) and audit *policy* (which action types exist, which require confirmation, each tool's parameter schema).

While the kernel and the pack share modules, the security story is unportable and the core cannot be tested in isolation — and the central claim of Constitution Principle III ("a pack cannot lower a guardrail") is only aspirational, because there is no boundary at which to enforce it. This feature draws that boundary, moves audit-specifics to the pack side, and makes "a pack cannot weaken a kernel guarantee" a tested property — **without** building a dynamic plugin system, since exactly one pack exists.

## User Scenarios & Testing *(mandatory)*

The "users" of this internal refactor are the people and mechanisms that depend on the boundary: the kernel maintainer who must reason about the core in isolation, the security (memory-injection) harness that must stay at zero Attack Success Rate, the existing audit + chat pipelines that must keep working, and a hypothetical future pack author who should be able to read the contract.

### User Story 1 - Kernel free of audit-specifics (Priority: P1)

As the kernel maintainer, I can point at the secure kernel and find **no** audit-specific knowledge in it — no concrete audit action-type names, no audit tool descriptions, no finding/severity/tag models, no planner stages, no audit privileged statuses. Everything task-specific lives on the pack side of an explicit boundary, and the separation is verifiable automatically rather than by inspection.

**Why this priority**: This is the structural deliverable and the tangible form of the project's goal (1). Until the kernel is free of audit knowledge, it is neither reusable nor testable in isolation, and none of the other stories can rest on a real seam.

**Independent Test**: An automated boundary check enumerates every kernel module's dependencies and asserts that none references a pack-side symbol; it reports 0 violations. A reviewer can also confirm the audit capability now enters the system through a single, explicit registration point.

**Acceptance Scenarios**:

1. **Given** the refactored codebase, **When** the boundary check runs, **Then** it reports zero kernel→pack references.
2. **Given** the kernel in isolation (pack not wired), **When** its core loop, validation mechanism, confirmation channel, memory, and guardrails are exercised, **Then** they operate without importing or naming any audit concept.
3. **Given** the audit capability, **When** the system is assembled, **Then** the audit pack is contributed at one known, explicit wiring point rather than being scattered through kernel modules.

---

### User Story 2 - A pack cannot weaken a kernel guarantee (Priority: P1)

As the security harness, I can prove that a capability pack — even a deliberately hostile one — cannot lower any kernel guardrail. A pack may register tools and mark its own actions high-risk, but it can never register a write/execute-class tool or a privileged-status change that skips out-of-band confirmation, never author or elevate content to the human-input trust tier, and never opt a tool out of whitelist validation, path-containment, or sandboxing.

**Why this priority**: Constitution Principle III states this is itself a security property that MUST be tested. Without it, the boundary is cosmetic — a pack could quietly become a memory-injection channel. This is the security heart of the feature and co-equal P1 with the structure that makes it enforceable.

**Independent Test**: A "hostile pack" fixture attempts each forbidden move; each attempt is rejected or rendered ineffective by the kernel, and the memory-injection harness Attack Success Rate remains 0.

**Acceptance Scenarios**:

1. **Given** a pack that registers a write/execute-class tool declared as "no confirmation needed", **When** an action for that tool is validated, **Then** the kernel still requires out-of-band confirmation (the requirement is derived by the kernel from action class, not taken on the pack's word).
2. **Given** a pack that attempts to emit content at the human-input trust tier, **When** that content enters the system, **Then** it is recorded no higher than external-model / tool-output tier and never drives control flow.
3. **Given** a pack tool with a missing or permissive parameter validator, **When** its action is validated, **Then** the kernel's whitelist, path-containment, and sandbox requirements still apply (fail-closed — a pack cannot widen access beyond kernel defaults).
4. **Given** any pack, **When** the full memory-injection harness runs, **Then** Attack Success Rate is 0.

---

### User Story 3 - No behavior change for existing pipelines (Priority: P2)

As a current user of the audit batch pipeline and of interactive chat mode, I observe no change: the same audit run produces the same findings and the same decisions, and chat answers the same questions the same way. This refactor is a re-layering and interface extraction, not a rewrite.

**Why this priority**: The value of the refactor is conditional on it being safe. This is the regression guarantee that lets the boundary land without disrupting delivered features 002 and 003.

**Independent Test**: The full existing test suite stays green with no reduction in passing tests; a representative audit run and a representative chat turn are behaviorally equivalent before and after.

**Acceptance Scenarios**:

1. **Given** the pre-refactor test suite result, **When** the suite runs after the refactor, **Then** the same tests pass (no net loss of green tests).
2. **Given** a fixed audit target, **When** it is analyzed before and after the refactor, **Then** the resulting findings and status decisions are equivalent.
3. **Given** a fixed chat question against a fixed project, **When** asked before and after the refactor, **Then** the routing, confirmation-gating, and grounded answer are equivalent.

---

### User Story 4 - The pack contract is documented (Priority: P3)

As a future pack author, I can read one document that tells me exactly what a pack provides to the kernel and exactly what the kernel guarantees regardless of my pack — without reading kernel internals. The document makes clear that no plugin registry exists yet and that a second pack would be wired explicitly, by the same mechanism the audit pack uses.

**Why this priority**: This makes the boundary legible and encodes the explicit YAGNI decision (document the interface; do not build extensibility infrastructure until a second pack exists). It is valuable but not blocking — the boundary and its security property (US1, US2) stand on their own.

**Independent Test**: A reviewer checklist confirms the document enumerates every element a pack contributes and every kernel guarantee it cannot alter, and states the no-registry decision.

**Acceptance Scenarios**:

1. **Given** the contract document, **When** a reviewer lists what a pack must supply, **Then** every provided element (tools, confirmation-required actions, escalation triggers, privileged-status set, parameter validators) is present.
2. **Given** the contract document, **When** a reviewer lists the invariants the kernel keeps, **Then** all trust invariants and the confirmation gate are present and marked as non-overridable by a pack.
3. **Given** the contract document, **When** a reviewer looks for extensibility infrastructure, **Then** it explicitly records that there is no dynamic registry/discovery/loader and that a second pack would be wired explicitly.

---

### Edge Cases

- **Dual-use primitive** (e.g. read a file, search code, write memory, request confirmation, escalate): stays on the kernel side as a task-agnostic primitive; the pack references the kernel primitive rather than duplicating it. Genuinely audit-specific capabilities (static analysis, PoC authoring, on-chain transaction analysis, planner stages) move to the pack.
- **Moving a shared data shape** (e.g. the concrete action-type enumeration) may invalidate previously-signed memory records. This is acceptable — memory is ephemeral and append-only, and records failing verification are silently dropped — consistent with the precedent set in feature 003.
- **A future pack needs a capability the kernel does not grant**: out of scope. The set of kernel guarantees is fixed; a pack can only add restrictions on top of them (mark more actions high-risk), never introduce new kernel-level powers.
- **Boundary check fails in CI**: the change does not ship. A kernel→pack reference has the same standing as a memory-injection regression — a hard gate, not a warning.
- **A pack registers a tool with no parameter validator**: the kernel still applies whitelist, path-containment, and sandbox defaults; the missing validator cannot widen access (fail-closed).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST contribute all task-specific capability to the kernel through a single explicit **capability-pack interface** — the pack supplies its tool definitions, the subset of its actions that require out-of-band confirmation, its domain escalation triggers, its domain privileged-status set, and its per-action parameter validators. The kernel consumes this interface and MUST NOT import or name pack-specific modules.
- **FR-002**: Kernel modules MUST NOT reference, import, or hardcode any audit-specific symbol — no concrete audit action-type value, no audit tool description, no finding/severity/tag model, no planner stage, no audit privileged-status. This separation MUST be verifiable by an automated boundary check that a reviewer can run.
- **FR-003**: The concrete audit action types (and their risk-class + reversibility metadata), the audit tool definitions, the audit per-action parameter validation, the audit escalation triggers, and the audit privileged-status confirmation set MUST all reside on the pack side of the boundary.
- **FR-004**: The kernel MUST retain sole ownership of every trust invariant — DATA-wrapping of all re-entering context, the SourceType trust hierarchy and the rule that model/relay output is never promoted to human-input, HMAC append-only memory, the out-of-band confirmation gate, the per-turn tool-call budget, path-containment, and sandboxed execution of attacker-influenced code. A pack contributes inputs to these mechanisms but MUST NOT replace, disable, or bypass any of them.
- **FR-005**: A pack MUST NOT be able to cause a write/execute-class action or a privileged-status change to execute without out-of-band human confirmation. The confirmation requirement MUST be derived by the kernel from the action's class, not accepted on the pack's declaration; any pack attempt to mark such an action as not-requiring-confirmation MUST be ineffective.
- **FR-006**: A pack (and any model output it produces) MUST NOT be able to author or elevate content to the human-input trust tier; such content MUST remain at external-model / tool-output tier at most and MUST NOT drive control flow.
- **FR-007**: Every pack-registered tool MUST remain subject to the same kernel validation mechanism used today — registry whitelist, parameter schema application, path-containment, and sandboxing for attacker-influenced execution. A pack MUST NOT be able to opt a tool out of these.
- **FR-008**: The system MUST NOT introduce a dynamic plugin registry, configuration-driven pack discovery, or runtime pack loading. The single audit pack MUST be wired explicitly at one known point.
- **FR-009**: The existing audit batch pipeline MUST produce equivalent findings and status decisions after the refactor as before (no observable behavior change on a fixed target).
- **FR-010**: Interactive chat mode (feature 003) MUST continue to function unchanged after the refactor — same routing, same confirmation-gating, same grounded answers on fixed inputs.
- **FR-011**: The full existing test suite MUST remain green with no net loss of passing tests, and the memory-injection harness Attack Success Rate MUST remain 0.
- **FR-012**: The boundary MUST place genuinely task-agnostic primitives (generic file read/search, memory write, confirmation request, escalation, local/relay reasoning transport) on the kernel side and audit-domain capabilities on the pack side; the placement of each capability MUST be explicit.
- **FR-013**: The pack contract MUST be documented such that a reader can enumerate everything a pack provides and everything the kernel guarantees — sufficient for a hypothetical second pack to be authored against it — and the document MUST record the explicit decision that no plugin registry is built.

### Key Entities

- **Secure Kernel**: the task-agnostic trust boundary and orchestration mechanism — the deterministic loop, the action-validation *mechanism*, the out-of-band confirmation channel, DATA-wrapped context assembly, HMAC memory, the guardrails and trust hierarchy, and the local-model / relay reasoning transport. Owns all invariants; knows nothing about any specific task domain.
- **Capability Pack**: a declarative bundle of task-specific capability. Provides: a set of tool definitions (name, description, action class, handler); the subset of its actions that require out-of-band confirmation; its domain escalation triggers; its domain privileged-status set; its per-action parameter validators. Constraint: it may add restrictions but cannot weaken any kernel guarantee.
- **Pack Interface / Contract**: the explicit, documented surface the kernel consumes from a pack, plus the fixed set of kernel guarantees that hold regardless of pack content.
- **Audit Pack**: the single concrete pack today — smart-contract audit. Contains the static-analysis / SmartGraphical / on-chain / PoC-authoring tools, the audit action types, the finding/severity/tag models, the planner stages, and the `{verified_safe, skip_analysis, audit_complete}` privileged-status set.
- **Boundary Check**: an automated verification that no kernel module depends on any pack module; a hard gate whose failure blocks the change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The automated boundary check reports **0** kernel→pack references.
- **SC-002**: After the refactor, the existing test suite has **no net loss of passing tests**, and the memory-injection harness Attack Success Rate is **0**.
- **SC-003**: In a hostile-pack test suite, **100%** of forbidden attempts (skip-confirmation on a write/execute action, author human-input-tier content, opt out of whitelist/containment/sandbox) are rejected or rendered ineffective.
- **SC-004**: A representative audit run and a representative chat turn each produce **behaviorally equivalent** results before and after the refactor (same findings/decisions; same routing/gating/answer).
- **SC-005**: The pack-contract document lists **100%** of the elements a pack provides and **100%** of the kernel guarantees a pack cannot alter, verified against a reviewer checklist.
- **SC-006**: **No** dynamic plugin registry, discovery, or runtime loader is added — verifiable by inspection: exactly one explicit pack wiring point and zero config-driven pack loading.

## Assumptions

- Exactly one capability pack (audit) exists; a second is hypothetical. Per Constitution Principle III (YAGNI), the boundary and interface are documented but no dynamic registry is built.
- The refactor preserves external behavior; it is re-layering plus interface extraction, not new capability. "Equivalent" means same findings/decisions and same chat routing/gating/answers on fixed inputs — not byte-identical artifacts (timestamps and ordering may differ).
- Kernel vs pack membership follows the enumeration in the feature input; the exact placement of a small number of dual-use read-only primitives is confirmed during planning, with genuinely task-agnostic file read/search remaining kernel primitives.
- Moving a shared data shape may require re-signing or dropping prior memory records; this is acceptable because memory is ephemeral and append-only (precedent: feature 003).
- No paid API is introduced or required (Constitution Principle V unchanged); the core loop continues to run on the local model or the manual relay.

## Dependencies

- Builds on features 001 (secure memory agent kernel), 002 (SmartGraphical integration), and 003 (interactive chat mode) — all kernel primitives and the chat loop already exist; the recurring gap has been wiring, not absence.
- Governed by Constitution v1.0.0, Principle III (Kernel / Capability-Pack Separation) as the driving authority, with Principles I, II, IV, and V as the guarantees a pack must not weaken.
