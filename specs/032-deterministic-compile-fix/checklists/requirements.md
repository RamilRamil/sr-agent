# Specification Quality Checklist: Deterministic Compile-Fixers in the Drafting Loop

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-21
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

- Internal harness feature: references existing components by name (`_fix_import_paths`,
  `_fix_nested_type_imports`, `_fix_address_interface`, `_targeted_hints`, `symbol_index`/`file_map`,
  `postfix_imports` event) — domain vocabulary, same convention as specs 024–031. The WHAT/WHY (the
  harness deterministically fixes the two dominant MECHANICAL compile errors instead of relying on a
  non-converging model) stays technology-agnostic.
- DATA-GROUNDED: the two chosen classes and the out-of-scope ones come from measured compile-error
  frequency across live GLM-5.2 + deepseek-v3.2 runs (undeclared ×8, address→interface ×3 in-scope;
  wrong-arg/invalid-token/instantiate-interface out). The eval-first discipline (spec 030) was applied
  — the scope follows the data, not a guess.
- Anti-invention invariant (FR-003) is the safety boundary and is explicitly tested (US2) — consistent
  with the project's no-invented-API discipline.
- No target material: all fixtures are invented contract/interface names + synthetic forge errors.
```
