# Specification Quality Checklist: Make via_ir Compilation Viable in the Harness Sandbox

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

- Requirements are behavior-level (a raised, configurable memory ceiling; the falsification copy carries the build cache). Concrete anchors (sandbox.py, the 512m default, `_MUTVERIFY_COPY_SKIP`, via_ir) live in the Context/Input as grounding, not in the requirement bodies, so the spec stays testable without pinning code structure.
- **Diagnosed from the artifact, triangulated three ways** — the 512m limit in code, `SIGKILL` in the captured error, and a clean-dir re-run giving 2/2 kills — so the root cause is proved, not guessed. FR-004/FR-012 make the memory VALUE empirical for the same reason (the session's recurring lesson: don't guess a constant).
- **Security is a first-class requirement (FR-009, SC-006), not a footnote.** The change touches sandbox-adjacent config, so the spec pins that no isolation invariant moves — memory is DoS-protection. The scoping (harness rises, secure agent unchanged) is guarded by a test (US3/FR-010) precisely because a silent leak or revert would be invisible.
- **Two parts, honestly separated by priority.** US1 (memory) is correctness — nothing works without it. US2 (cache in the falsification copy) is cost, but done now because falsification is the most frequent cold-build site, so it is both the biggest residual OOM risk and the dominant eval cost.
- The empirical calibration (FR-012/SC-001/SC-007) is explicitly a live operator step, not an offline unit test — offline tests cannot run the memory-heavy build. The offline tests cover the scoping and the copy change deterministically.

### Revision — /speckit-analyze remediations

- **A1**: the live calibration (T013) now separates the harness-free raw-build memory PROOF (step 1, no confound) from the end-to-end `--only 4` re-run (step 2), and flags that step 2 can hit the SEPARATE spec-026 id-scheme fragility (`only_ids_not_found`) — a retry condition, not a 027 memory failure. This keeps the calibration from conflating two distinct bugs.
- **A2**: T013 now closes the FR-004 loop explicitly — record the smallest surviving ceiling and, if it is not the `6g` starting default, update `_harness_sandbox` (T004) to the calibrated value.
- **A3**: T006 now pins the real contract — `_MUTVERIFY_COPY_SKIP` is the `ignore_patterns` callable `fn(dir, names) -> ignore-set`, called and asserted directly.

