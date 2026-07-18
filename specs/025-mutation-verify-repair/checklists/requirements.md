# Specification Quality Checklist: Make Falsification-Verification Actually Run

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-16
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification


## Notes

- Function names, error codes and tool names are kept out of the requirement bodies; they appear only as grounding context. The mechanism is described by behavior ("falsification step", "illustrative fix block"), so the requirements stay testable without pinning code structure.
- **The load-bearing property is US3 (refuse rather than guess), not US2 (reconstruct).** A wrong reconstruction produces a *wrong* verified signal, which is worse than the current no-op — the operator would trust it. SC-003 pins refusal in 100% of defined uncertainty cases, and FR-005/FR-007/FR-009 are written as prohibitions for that reason.
- **The spec deliberately under-sells.** A dedicated "Honest expectations" section records that the *report channel* tops out at 3 of 23 tasks, that one of those 3 is expected to refuse by design, and that a previously-reported milestone overstated its evidence. Stated in the spec itself so no reader mistakes a mechanism fix for a coverage fix.

### Revision — the "unverifiable forever" error (caught by the user)

The first draft claimed findings without a report diff were unverifiable *forever*, and priced the whole feature at a 3-of-23 ceiling. That was wrong: it mistook **one source of fixes for the only one**. The falsification invariant needs *a* fix, not *the report's* fix — and the operator can write one for any finding, deterministically and with no model, which is the project's highest-trust source and squarely within its human-authority principle. US2 (operator-supplied patch) was added as a result, and the ceiling framing was corrected throughout.

This is the same failure mode as two earlier errors in this session's work: stating a conclusion more strongly than the evidence licensed. Recorded here rather than quietly patched, because the spec's credibility depends on its limits being real.

Consequence worth keeping visible: **18 of 23 tasks in a real run are leads** — hypotheses whose passing proof is their only evidence, and which never carry a report fix. They are exactly where unverified passes are most dangerous, and only the operator channel reaches them.
- The existing no-fuzzy-patching rule is revisited in a dedicated section rather than silently bypassed: reconstruction-from-an-illustration is a different operation than fuzzy-applying a real patch, and FR-005/FR-007 make it strictly stricter than the tooling. Recorded as a deliberate narrowing.
- Verified against the live artifact, not recollection: both patch tools were actually run against the real fix block and both rejected it (exit 128 / exit 2). That evidence is what the Context section reports.
