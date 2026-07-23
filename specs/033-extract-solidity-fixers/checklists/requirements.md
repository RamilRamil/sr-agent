# Specification Quality Checklist: Extract the Deterministic Solidity Compile-Fixer Layer

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-23
**Feature**: [spec.md](../spec.md)

## Content Quality

- [X] No implementation details (languages, frameworks, APIs)
- [X] Focused on user value and business needs
- [X] Written for non-technical stakeholders
- [X] All mandatory sections completed

## Requirement Completeness

- [X] No [NEEDS CLARIFICATION] markers remain
- [X] Requirements are testable and unambiguous
- [X] Success criteria are measurable
- [X] Success criteria are technology-agnostic (no implementation details)
- [X] All acceptance scenarios are defined
- [X] Edge cases are identified
- [X] Scope is clearly bounded
- [X] Dependencies and assumptions identified

## Feature Readiness

- [X] All functional requirements have clear acceptance criteria
- [X] User scenarios cover primary flows
- [X] Feature meets measurable outcomes defined in Success Criteria
- [X] No implementation details leak into specification

## Notes

- **REVISED after a review caught an internal contradiction**: the original spec claimed BOTH "remove
  the duplication between the two repair loops" AND "zero functional change". Those cannot both hold —
  the five transform-application sites have divergent sequences (the in-place drafting step never runs
  `import_paths`; `import_paths` runs with a different base in synthesis), and unifying them WOULD change
  behavior, while the existing unit tests pin fixers individually (not the sequence). So this spec is now
  the honest NO-OP: MOVE the fixer functions + PIN each site's sequence with characterization tests.
  Any UNIFICATION is deferred to a separate, explicitly-measured spec (034).
- Oracle = the EXISTING suite passing UNCHANGED + new characterization tests that capture the sequences
  before any future change. Strongest possible bar for a pure move.
- Names of internal components appear because they ARE the subject of the move — domain vocabulary.
- Motivated by an evidenced structural risk: the import-path bug class recurred 3× in one day (memory
  `project_poc_runner_monolith`); consolidating the FUNCTIONS fixes the logic-bug cause at the function
  level, and the characterization tests make the future sequence-unification safe.
- No target material: a refactor of harness code; fixtures are invented/synthetic forge shapes.
- **REVISED AGAIN (3rd review)**: (1) the cohesion assumption was FALSE — fixers share low-level helpers
  (`_tracked_sol`/`_SKIP_DIRS`/`_path_for`/`_strip_comments`) with grounding/`_poc_defects`/scaffold code,
  so a "move only the fixers" is impossible without a circular import → FR-011 introduces a shared
  low-level utils module (a bundled, acknowledged second behavior-preserving move; touches `_poc_defects`
  ONLY at its import line). (2) the five sequences are INLINE inside `synthesize_scaffold`/`_process_finding`
  so they can't be tested in isolation → FR-012 extracts each into its own named sequence-function
  (behavior-preserving, NOT unification), which FR-005 characterization tests target and FR-009 keys on
  BY NAME (stable structural invariant, not brittle line numbers). This makes US2 actually implementable
  and the site-inventory an enforced invariant.
- A dependency inventory (FR-011) MUST precede tasks.md, so the module boundary is decided with evidence,
  not blindly at implementation time (where it would most likely become a circular import).
```
- **REVISED AGAIN (4th review — bootstrap gap)**: the guardrail could not protect the step that CREATES
  it — FR-005a wanted characterization tests green on the "pre-move tree", but they call the named
  sequence-functions which only exist AFTER FR-012's extraction (the riskiest step: rewriting two of the
  harness's largest functions), leaving that step uncovered. Fixed: FR-013 names FOUR independently-green
  commits with each step's guarantee stated; FR-014 adds a TEMPORARY differential test (inline vs
  extracted, byte-identical) that gates the extraction commit and is removed next. SC-009/SC-010 give
  FR-011/FR-012 real acceptance (no import cycle; named functions exist + loops call them + differential
  was green). Out of Scope corrected: this is NOT "only the fixer functions" — it moves shared helpers +
  edits two loop bodies; the boundary is "no LOGIC/sequence change", not "one file". SC-006's no-op-diff
  bar now applies PER COMMIT.
