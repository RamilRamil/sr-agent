# Specification Quality Checklist: Pin the Finding for the Proof-Eval

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-19
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

- Requirements are behavior-level (a task-list input that bypasses extraction; a curated finding in the case). The concrete anchors (`--tasks-from`, `_extracted_tasks.json`, `extract_tasks`, `extract_fix_for_finding`, `proof_bench.load_case`) live in the Context/Input as grounding, not in requirement bodies, so the spec stays testable without pinning code structure.
- **The framing is deliberately "decouple + pin," not "fix a bug."** The Context makes explicit that the id-scheme nondeterminism is NOT a general harness defect (normal runs are self-consistent) — it bites only the eval's fixed-external-id-vs-fresh-extraction situation. This keeps the scope honest and prevents over-building a general fuzzy-matcher (Out of Scope).
- **The deeper justification is measurement hygiene, not just the id.** FR-009/SC-002/SC-007 pin that the finding's TEXT is constant across runs — because even a normalized id would leave extraction's title/description variance in the number. Removing extraction from the measured path is the two-axis-separation principle from spec 026 US4 applied.
- **Ground truth stays human + model-free** (FR-007/FR-008): the curated finding is transcribed by a human like the discovery benchmark's labels and like the operator fix; a missing field is a loud load error, never a silent fallback to the very extraction this feature removes. This mirrors the project's standing "ground truth is human, not model" discipline.
- The default operator path is explicitly untouched (FR-006/SC-003) — the general harness still extracts with the model; only the eval opts into pinning.

### Revision — /speckit-analyze remediations

- **A1 (error handling)**: the `--tasks-from` branch sits INSIDE main()'s existing `try/except`, so a malformed/absent task file aborts cleanly as `extract_failed` (T007) — pinned by a new test (T004b), not a raw traceback.
- **A2 (clarity)**: `--report` stays REQUIRED with `--tasks-from` — the report-fix path (`extract_fix_for_finding`) and reconstruction still read it; `--tasks-from` bypasses ONLY the model task extraction. Noted in T006/T007.
- **A3 (cosmetic)**: the `extract_start` event fires even when pinned; harmless (proof_bench does not key on it) — keep it or emit a `tasks_loaded` variant, not a blocker.

