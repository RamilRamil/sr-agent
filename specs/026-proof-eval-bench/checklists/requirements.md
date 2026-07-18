# Specification Quality Checklist: Proof-Pipeline Eval

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-18
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

- The two metrics are described by behavior (an interval that widens with smaller N; a monotonic funnel with named casualties), not by method — the exact interval computation is a planning detail, but the load-bearing PROPERTIES (widens with N, supports an overlap test, deterministic) are pinned as requirements so they stay testable.
- **US3 (cannot inflate itself) is the load-bearing story**, mirroring the discovery benchmark's matcher and the vacuous-PoC gate. The verified count counts exactly what the harness reports and nothing more; a model anywhere in scoring is disqualified. SC-005 pins "never more".
- **Contamination honesty is a first-class requirement, not a footnote** (FR-014, SC-008): the tool must state in its own output that strata-bb is a tuned-on DEV set measuring within-set regression/progress, not absolute capability — so a dev number is never mistaken for a capability number. This is the antidote to the "3/5 vs 2/5" misread that motivated the feature.
- **Experimental hygiene is enforced, not advised** (US4): the run-configuration record + mismatch flag exist precisely because the motivating failure was an unattributable delta across configs that differed in more than the harness version.
- Statistics grounded in captured 2026 practice (Bayes@N / "don't pass@k"): a single run is not decidable; a winner is declared only on separated intervals. The spec fixes the property, not the estimator.

### Revision — /speckit-analyze remediations

- **A1 (the lead/fix contradiction), resolved by the user's lifecycle framing.** The first draft both required a fix per case (FR-008) AND contemplated a fix-less "lead case" (edge case) excluded from the denominator — incompatible. Resolved: a lead is NOT an eval case; it is PROMOTED to a confirmed fix-bearing finding (then it enters the set like any other case) or DISCARDED — no permanent lead limbo. FR-008 is now unconditional, `is_lead` is dropped from the model, and FR-009 is satisfied structurally (leads never load). This matches how leads are actually handled: drive them to a vulnerability or reject them.
- **A2/A3**: the `_stage_of` event→stage mapping (the fragile coupling to the runner's real event shapes) now has DIRECT tests over raw event streams (T016b) and a membership test (T016c) — a case counts as "extracted" only when its finding_id is among the `extracted` event's ids, because extraction emits all of them. This mirrors reconstruct's "test the real contract, not a paraphrase" rule.
- **A4**: `CaseOutcome.stage == verified` IFF `outcome == passed_verified`, commented and pinned, so the funnel's top and the interval's numerator cannot drift apart.

All checklist items re-validated after the revision — 16/16 pass; no [NEEDS CLARIFICATION] introduced.
