# Feature Specification: SmartGraphical Integration

**Feature Branch**: `002-smartgraphical-integration`

**Created**: 2026-07-01

**Status**: Draft

**Input**: User description: "Integrate SmartGraphical (the user's own auditor-centric structural + logic analysis engine) into SR-agent as a third deterministic analysis engine, complementary to Slither (syntactic) and Mythril (symbolic)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Logic-level findings from a third engine (Priority: P1)

When an audit runs, the agent should additionally analyze each contract with SmartGraphical's
logic rules (stake/unstake symmetry, withdraw preconditions, sensitive call ordering, advanced
DeFi reentrancy, taint) and surface those findings in the report alongside Slither and Mythril.
This catches *business-logic* vulnerabilities that the syntactic (Slither) and symbolic (Mythril)
engines structurally miss.

**Why this priority**: This is the immediate, standalone value — a whole new class of findings
with no dependency on the other goals. It is the MVP: even if nothing else ships, the audit
gains logic coverage.

**Independent Test**: Run an audit on a contract with a logic flaw the other engines miss (e.g.
a withdraw with no precondition, or a price-read-then-transfer ordering). Assert the report
contains a SmartGraphical-attributed finding for it, stored as a tool-output finding.

**Acceptance Scenarios**:

1. **Given** a contract with a withdraw lacking preconditions, **When** an audit runs with
   SmartGraphical available, **Then** the report contains a SmartGraphical logic finding for that
   function, attributed to its engine, with category/confidence metadata.
2. **Given** SmartGraphical is unavailable (not installed / not reachable), **When** an audit
   runs, **Then** the audit completes normally using the other engines and notes that the
   SmartGraphical pass was skipped.

---

### User Story 2 - Accurate interference graph for combination (Priority: P2)

The agent's Stage 3 combination step should use SmartGraphical's structural graph (per-function
read/write state accesses, function-to-function calls, cross-contract/inheritance calls) instead
of the current regex heuristic, so that findings are combined only when their functions genuinely
share state — including across inheritance and multiple files.

**Why this priority**: It materially improves combination accuracy (fewer false chains, catches
cross-file interactions) but depends on the structural model being available and is a refinement
of an existing capability rather than net-new coverage.

**Independent Test**: On a two-contract inheritance example where a child function and a parent
function share state, assert the graph marks them as interacting and Stage 3 links the
corresponding findings — a case the single-file regex graph misses.

**Acceptance Scenarios**:

1. **Given** a multi-file project with inheritance, **When** the interference graph is built from
   SmartGraphical, **Then** functions sharing state across the inheritance boundary are reported
   as interacting.
2. **Given** SmartGraphical's graph is unavailable, **When** Stage 3 runs, **Then** it falls back
   to the existing heuristic graph without error.

---

### User Story 3 - Findings remain unconfirmed hypotheses (Priority: P3)

Every SmartGraphical finding must enter the system as a deterministic *hypothesis* (medium
confidence, false-positive-prone by design) that flows through the same guardrails as any other
finding and is only ever confirmed by Proof-of-Code execution — never auto-trusted because a
tool emitted it.

**Why this priority**: It preserves the security invariant. It is lower priority only because it
is a constraint on US1/US2 rather than a separately demonstrable journey.

**Independent Test**: Ingest a SmartGraphical finding and assert its stored status is not
"confirmed" and that confirming it requires a passing PoC.

**Acceptance Scenarios**:

1. **Given** a SmartGraphical finding is ingested, **When** it is stored, **Then** its provenance
   is tool-output and its status is unconfirmed (no PoC has run).
2. **Given** a SmartGraphical finding carries a manipulative-looking message, **When** it is
   ingested, **Then** the message is sanitized like any other external content.

### Edge Cases

- What happens when SmartGraphical produces a finding whose category has no mapping to the
  agent's vulnerability taxonomy? (It is stored with no taxonomy tag, not dropped.)
- What happens when SmartGraphical and Slither both report the same issue at the same location?
  (Both are kept with engine attribution; the report may group them, but neither is silently
  dropped — hiding a corroborating signal would be worse than a duplicate.)
- How does the system handle a contract SmartGraphical cannot parse (returns no model)? (The
  pass yields zero findings for that file and the audit continues.)
- What happens on a single-file audit with no inheritance? (US2 graph degrades gracefully to the
  same result as the heuristic; US1 findings still apply.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST analyze each Solidity file in the audit scope with SmartGraphical
  and ingest its resulting findings.
- **FR-002**: Each ingested SmartGraphical finding MUST be stored as a finding with tool-output
  provenance (the trust level used for deterministic analyzers), carrying its rule identifier,
  category, confidence, human-readable message, remediation hint, and source location
  (file + function + line where available).
- **FR-003**: The system MUST translate SmartGraphical's confidence and category into the agent's
  own severity and vulnerability-taxonomy fields, leaving the taxonomy tag empty when no faithful
  mapping exists rather than inventing one.
- **FR-004**: The SmartGraphical pass MUST run within the existing deterministic static-analysis
  step alongside the other analyzers, MUST be best-effort, and MUST auto-skip (never abort the
  audit) when SmartGraphical is unavailable or errors.
- **FR-005**: When SmartGraphical's structural model is available, the system MUST build the
  interference graph from its per-function read/write state accesses and call edges (including
  function-to-function and cross-contract/inheritance edges); otherwise it MUST fall back to the
  existing heuristic graph.
- **FR-006**: Stage 3 combination MUST consume the SmartGraphical-derived graph for its
  interference and reentrancy-adjacency decisions when that graph is present.
- **FR-007**: SmartGraphical findings MUST pass through the same guardrails as other external
  content (note sanitization, severity conjunction) and MUST NOT be auto-confirmed; confirmation
  of any finding remains gated on Proof-of-Code execution.
- **FR-008**: The audit report MUST attribute each finding to the engine that produced it
  (Slither / Mythril / SmartGraphical / relayed model), so the auditor can see provenance.
- **FR-009**: The system MUST support a project that spans multiple Solidity files with imports
  and inheritance as a single audit scope for the SmartGraphical structural pass.
- **FR-010**: The integration MUST be controllable (it can be turned off) and MUST default to a
  configuration that keeps existing single-engine and relay behavior working unchanged.

### Key Entities *(include if feature involves data)*

- **SmartGraphical Finding**: A logic/structural hypothesis emitted by SmartGraphical — rule id,
  title, category, confidence, portability, message, remediation hint, and evidence (contract,
  function, statement, line). Maps onto the agent's Finding.
- **Structural Graph**: SmartGraphical's normalized call/state model — per-function read/write
  state accesses, guards, external calls, and typed call edges (function-to-function,
  state-to-function, cross-contract). Feeds the agent's interference graph.
- **Engine Attribution**: The provenance label on a finding identifying which analyzer produced
  it, surfaced in memory and the report.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On an example DeFi-style contract, the audit surfaces at least one logic-level
  finding attributable to SmartGraphical that neither Slither nor Mythril produces, demonstrating
  complementary coverage.
- **SC-002**: On a two-contract inheritance example where a child and a parent function share
  state, the SmartGraphical-derived interference graph marks them as interacting and Stage 3
  links the corresponding findings — a result the heuristic single-file graph does not produce.
- **SC-003**: When SmartGraphical is unavailable, 100% of audits still complete and produce a
  report (the pass degrades to a skip with no error).
- **SC-004**: 100% of SmartGraphical findings enter the system as tool-output hypotheses and none
  reach "confirmed" status without a passing Proof-of-Code, preserving the security invariant.
- **SC-005**: Every finding in the report shows its producing engine, so an auditor can trace any
  finding to Slither, Mythril, SmartGraphical, or a relayed model in 100% of cases.

## Assumptions

- SmartGraphical is the user's own code; vendoring, library import, or external-tool invocation
  are all acceptable integration mechanisms, chosen on engineering merit rather than licensing.
- SmartGraphical exposes a stable machine-readable output (findings + structural graph) suitable
  for programmatic consumption.
- Solidity is the in-scope language for this feature; SmartGraphical's other language targets
  (C, Rust) are out of scope here.
- The agent's existing Finding model, memory provenance levels, guardrails, Stage 3 combination,
  report generator, and Proof-of-Code verification path are reused, not redesigned.
- SmartGraphical findings are heuristic and false-positive-prone (per its own documented
  trade-offs); the agent's value-add is treating them as hypotheses to be verified, not as
  ground truth.
- Deduplication across engines is best-effort grouping in the report, not a hard requirement to
  remove overlapping findings.
