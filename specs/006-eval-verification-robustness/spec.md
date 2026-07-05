# Feature Specification: Eval/Verification Robustness for Generated-Artifact Success Gates

**Feature Branch**: `006-eval-verification-robustness`

**Created**: 2026-07-05

**Status**: Draft

**Input**: User description: "Eval/verification robustness for generated-artifact success gates (SR-agent). Motivation: on 2026-07-05, the PoC-workability harness's compile-success detector (`_compiled()` in scripts/poc_queue_runner.py) was implemented as a DENYLIST — it returned "compiled" whenever the forge output did NOT contain a small fixed set of known failure phrases. A real compile failure with a different message was not on the denylist, so the detector silently misreported 3/3 genuine compile failures as successes — producing a false "all findings compiled" milestone that was only caught by chance. The EVAL BUG (the denylist detector) is the general, recurring risk this feature addresses. Scope: (1) establish and document a general principle for any automated correctness/success gate over generated artifacts in this repo — positive-signal detection preferred over denylist detection, with a required cross-check before recording a milestone; (2) audit the existing PoC-workability harness for other single-signal/denylist checks and correct or justify each; (3) research whether SmartGraphical's call-graph analysis can serve as a stronger, non-regex mechanism check, with a clear adopt/adapt/defer recommendation; (4) deliver durable, documented spec + design docs, not a one-off patch."

## User Scenarios & Testing *(mandatory)*

The "user" of this feature is the **operator/maintainer** who runs SR-agent's automated
tooling (today: the PoC-workability harness) and who reads/relies on its reported
outcomes and any documentation (roadmap, memory) built from them.

### User Story 1 - Trust that a reported success is real (Priority: P1)

As the operator, when the harness tells me a generated PoC "compiled" (or any other
automated check reports success), I need that verdict to be based on genuine evidence
of success — not merely the absence of error text the tool's author happened to
anticipate — so that I never build a decision, a further pipeline step, or project
documentation on a false positive.

**Why this priority**: This is the exact failure that just occurred and produced a
false "all findings compiled" milestone recorded in project docs. It is the
highest-priority risk because it is silent — nothing alerts the operator that the
verdict is wrong, unless they independently re-derive it.

**Independent Test**: Feed the harness's compile-check a `forge` transcript containing
a genuine, previously-unseen-format compiler error (not one of the historically known
failure phrases). The check must report failure, not success. This is testable without
touching any other part of the harness.

**Acceptance Scenarios**:

1. **Given** a tool transcript that represents a genuine failure using wording the
   check's author never anticipated, **When** the automated check evaluates it,
   **Then** it reports failure (not success).
2. **Given** a tool transcript that represents genuine success, **When** the automated
   check evaluates it, **Then** it reports success (the fix must not trade false
   positives for false negatives).
3. **Given** an automated check reports success, **When** the operator asks "was this
   independently corroborated?", **Then** the answer is documented and verifiable —
   not "we trusted the one signal."

---

### User Story 2 - Know that every existing automated check in the harness is sound (Priority: P1)

As the operator, I need every existing automated success/failure check in the
PoC-workability harness (not just the one that broke) reviewed against the same
failure mode, so a similar silent false positive isn't waiting in a different check.

**Why this priority**: A single fixed bug does not establish that the harness is
otherwise sound. The incident revealed a *pattern* (denylist / single-signal
verification), and the pattern could recur anywhere else similar reasoning was applied.

**Independent Test**: Produce a checklist enumerating every automated verdict-producing
check in the harness, each marked either "uses a positive success signal" or "justified
exception" with a stated reason. The checklist itself is inspectable and complete
without running any code.

**Acceptance Scenarios**:

1. **Given** the harness's existing checks (compile detection, the structural
   PoC-quality gate, the diagnostic mechanism signal, and any other verdict-producing
   check), **When** each is reviewed, **Then** each is either corrected to a
   positive-signal approach or has a documented, explicit justification for why a
   different approach is acceptable there.
2. **Given** a check that is intentionally non-blocking/diagnostic-only, **When** it is
   reviewed, **Then** its diagnostic (not decision-gating) status and its known blind
   spots are explicitly documented, so it is never later mistaken for a hard gate.

---

### User Story 3 - Decide whether a stronger, structural mechanism check is worth adopting (Priority: P2)

As the operator, I need a clear, reasoned recommendation on whether SmartGraphical's
call-graph analysis is worth integrating as a stronger replacement for the current
best-effort text-pattern check of "does the generated PoC actually exercise the
finding's specific function," so I can decide with evidence rather than guessing.

**Why this priority**: This directly targets the one class of correctness gap current
tooling still cannot verify well (whether a PoC's mechanism actually matches the
finding) — but it depends on an external tool not currently installed in this
environment, so the decision itself (not just a description) is the deliverable.

**Independent Test**: Read the produced recommendation without running any code; it
must state a clear adopt/adapt/defer position, the reasoning, and what would change the
recommendation (e.g., availability of the external dependency, cost/benefit versus the
current heuristic).

**Acceptance Scenarios**:

1. **Given** SmartGraphical's documented capabilities and its current integration
   status in this project, **When** the research is complete, **Then** a single clear
   recommendation (adopt / adapt / defer) is produced with supporting reasoning.
2. **Given** the recommendation is "defer" or "adapt", **When** the operator reads it,
   **Then** the current heuristic's known limitation (documented in User Story 2) still
   stands, clearly labeled as a known, accepted gap — not silently unresolved.

---

### User Story 4 - Have this durably documented, not just patched (Priority: P2)

As a future contributor (or the operator returning after time away), I need the
general principle ("why denylist checks are dangerous, what to do instead") and the
concrete decisions from this feature to be findable in the project's documentation, not
only inferable from a code diff or a chat transcript.

**Why this priority**: Without durable documentation, the same mistake is likely to
recur in a future capability pack or tool, because the lesson lives only in a
now-fixed piece of code and nobody's memory.

**Independent Test**: A new contributor, given only the repository's documentation (not
this conversation), can find the principle, know which existing checks were reviewed
and why, and see the SmartGraphical recommendation with its reasoning.

**Acceptance Scenarios**:

1. **Given** the project's existing documentation structure (kernel vs. audit-agent
   docs, roadmap), **When** this feature is complete, **Then** the general principle and
   the concrete decisions are placed in the appropriate existing document(s) or a new
   one, discoverable from the top-level docs.
2. **Given** the previously-recorded false milestone in project documentation, **When**
   this feature is complete, **Then** that record is corrected to reflect the honest,
   re-verified state.

### Edge Cases

- What happens when the wrapped tool (e.g., `forge`) changes its output format in a
  future version, and neither the old failure phrases nor the new success marker match
  exactly? → The check MUST fail closed (report failure/unknown, never silently report
  success) so a new format is caught rather than silently misclassified.
- What happens when the "positive success signal" itself could theoretically appear in
  a failure transcript by coincidence (e.g., partial output)? → The cross-check
  requirement (an independently-computed second signal, not a re-derivation of the same
  transcript) exists precisely to catch this; a single signal, however well-chosen, is
  never treated as sufficient for a documented milestone claim.
- What happens if SmartGraphical's external dependency is unavailable in a given
  environment even after a decision to adopt it? → The feature's recommendation must
  address this explicitly (e.g., graceful non-blocking degradation), not assume the
  dependency is always present.
- What happens to work (documented milestones, decisions) that already depended on the
  flawed check before this feature existed? → It must be identified and corrected as
  part of this feature, not left inconsistent with the corrected checks.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every automated success/failure verdict over a generated artifact in this
  repository MUST be based on a positive, well-defined signal that can only appear on
  genuine success, not on the absence of an anticipated set of failure signals.
- **FR-002**: Before an automated success verdict is recorded as a milestone or success
  claim in project documentation, it MUST be corroborated by at least one
  independently-computed second signal (not a re-derivation of the same single check).
- **FR-003**: Every existing automated verdict-producing check in the PoC-workability
  harness MUST be reviewed; each MUST either be corrected to use a positive success
  signal or have an explicit, documented justification for why its current approach is
  acceptable.
- **FR-004**: Any check that is intentionally diagnostic/non-blocking (does not gate an
  outcome) MUST be explicitly labeled as such, including its known limitations, so it
  cannot later be mistaken for a hard correctness gate.
- **FR-005**: A feasibility assessment of using SmartGraphical's call-graph analysis as
  a stronger mechanism-verification signal MUST be produced, ending in one clear
  recommendation (adopt / adapt / defer) with supporting reasoning.
- **FR-006**: The general principle (positive-signal over denylist detection, mandatory
  cross-check before recording success claims) and the concrete decisions from this
  feature MUST be captured in durable project documentation, discoverable from the
  project's existing top-level docs.
- **FR-007**: Any previously-recorded documentation (e.g., roadmap milestone entries)
  that relied on the flawed check MUST be corrected to reflect the honestly re-verified
  state.
- **FR-008**: Corrections made under this feature MUST NOT introduce new false
  negatives (genuinely successful artifacts being reported as failed) — the fix must be
  verified against both a known-good and a known-bad case.

### Key Entities

- **Success Gate**: An automated check that produces a binary (or graded) verdict over
  a generated artifact (e.g., "did this PoC compile", "did this PoC pass", "is this PoC
  structurally real"). Has a signal type (positive-signal vs. denylist), a
  blocking/diagnostic status, and — where blocking — a documented justification if it
  is not (yet) positive-signal-based.
- **Cross-Check**: A second, independently-computed signal used to corroborate a
  Success Gate's verdict before that verdict is trusted for a documented claim.
- **Mechanism-Verification Recommendation**: The documented adopt/adapt/defer decision
  on using SmartGraphical (or an equivalent structural analysis) as a stronger
  mechanism-check signal, with its reasoning and the conditions that would change it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of automated verdict-producing checks in the PoC-workability harness
  are inventoried, and each is either positive-signal-based or carries an explicit,
  written justification for not being so.
- **SC-002**: Zero success claims in project documentation going forward are recorded
  from a single uncorroborated automated signal; the cross-check requirement is
  documented as a standing rule, not a one-time action.
- **SC-003**: The SmartGraphical feasibility question reaches one unambiguous
  recommendation (adopt / adapt / defer), stated in a single sentence a reader can quote,
  with its reasoning traceable in the documentation.
- **SC-004**: The previously-recorded false "all findings compiled" milestone is
  corrected in project documentation within this feature's completion, and the honest
  current state is recorded in its place.
- **SC-005**: Re-running the corrected checks against both the known-false-positive
  transcript (the incident) and a known-genuine-success transcript produces the correct
  verdict in both cases (no regression toward false negatives).

## Assumptions

- The "operator" acting as the user in these scenarios is the person running SR-agent's
  tooling (today, primarily the PoC-workability harness) — this is an internal
  reliability/quality feature, not an end-user-facing product feature, so its "user
  scenarios" describe a maintainer's needs rather than an external customer's.
- This feature concerns any current or future automated success/failure verdict over a
  generated artifact in this repository (PoC compilation/execution today; potentially
  findings extraction or other capability-pack tooling later) but its immediate,
  in-scope audit target is the existing PoC-workability harness
  (`scripts/poc_queue_runner.py`) — a future pack's tooling is covered by the
  documented *principle*, not by re-auditing code that doesn't exist yet.
- SmartGraphical's external installation is not present in this environment; the
  research and recommendation in User Story 3 can be produced from its existing
  integration code and documentation (`sr_agent/packs/audit/tools/smartgraphical.py`,
  `specs/002-smartgraphical-integration/`) and reasoning about its capabilities, without
  requiring the dependency to be installed and run end-to-end in this pass.
- "Durable documentation" means the project's existing docs structure
  (`docs/kernel.md`, `docs/audit-agent.md`, `docs/roadmap.md`) or a clearly-linked new
  document — not only this feature's own `spec.md`, which is a planning artifact, not
  the place operators look for standing project knowledge.
- No new plugin/registry system for verification backends is in scope (matches this
  project's established YAGNI stance from spec 004); if SmartGraphical is adopted, it is
  wired in directly, the same way the audit pack is wired into the kernel.
