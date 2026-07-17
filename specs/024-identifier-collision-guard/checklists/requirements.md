# Specification Quality Checklist: Deterministic Repair Guard for "Identifier Already Declared"

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

- The requirements stay behavior-level: the "deterministic hint layer" is described by what it does, not by its code location. Error codes appear only as grounding context, never as a requirement's subject — FR-006 makes that explicit after the live log proved the originally-assumed code (2333) was simply wrong (real: 9097).
- Anti-inflation firing (US2) mirrors the project's standing matcher discipline; it is the load-bearing safety property and is covered by dedicated negative acceptance scenarios.

### Revisions

**Rev 2 — live-log evidence (`poc_run.log`)**. Grounding the spec in captured compiler output instead of
recollection overturned two premises: the error code, and the belief that finding-2 was an invented API
(it was a real base state variable reached through a wrong qualifier). US3 was added, the false
"invented API" out-of-scope claim removed, and two live traps pinned as edge cases (lowercase-initial
type; differing collided types).

**Rev 3 — `/speckit-analyze` remediations**. FR-003 rewritten: the declaring location now comes from the
compiler's own output rather than from re-parsing the scaffold — analysis found `_scaffold_base_name` is
per-file by contract while the layer receives a multi-file blob, so the original approach could have
named the WRONG base (the misleading specific claim FR-004 exists to prevent). FR-008 now requires
stripping comments before the evidence gate. FR-014 added (per-error-code test layout, matching the
existing `test_targeted_hints_2904.py`). The incoherent "ambiguity suppression" edge case was dropped:
the 9582 error's own precondition is that the compiler has already ruled the qualified access out, so
suppressing on that basis would withhold a correct hint.

All checklist items re-validated after Rev 3 — 16/16 pass; no [NEEDS CLARIFICATION] introduced.
