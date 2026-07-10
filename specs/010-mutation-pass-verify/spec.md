# Feature Specification: Mutation-Based PASS Verification

**Feature Branch**: `010-mutation-pass-verify`

**Created**: 2026-07-06

**Status**: Draft

**Input**: User description: "Mutation-based PASS verification for the PoC-workability harness (turn mechanism_signal from a heuristic into a real correctness gate). This session repeatedly produced PoCs that COMPILE and PASS yet do not prove the finding — the sharpest example (2026-07-06): a structurally-clean, defect-free, forge-PASSING H-01 PoC named `testRevertWhenRequestRedeemWithZeroShares` with ZERO relation to the actual exploit, caught only by a human reading the code. The `context-foundry-poc` invariant: a genuine exploit PoC's assertion must FAIL if the described bug were fixed. Scope: (1) extract each finding's suggested fix (the inline unified-diff `**Fix**` block) during extraction; (2) when a PoC reaches a genuine PASS, re-run it against a patched copy of the source — still passes → downgrade to `unverified_pass`; now fails → confirm as verified; (3) honest fallback `mutation_verify_unavailable` when no applicable fix / diff doesn't apply; (4) validate offline via the spec-009 fake harness, live H-01 optional. Out of scope: generating a fix (Stage 1); scaffold synthesis; kernel changes; making mutation-verify a precondition for writing a PoC; clever fuzzy diff application. Step 2 of the harness-review remediation (step 1 = spec 009)."

## User Scenarios & Testing *(mandatory)*

The "user" is the SR-agent **operator/maintainer** of the PoC-workability harness —
internal reliability work. It follows the eval-robustness doctrine of
[docs/eval-principles.md](../../docs/eval-principles.md): a success verdict must rest
on a signal that can ONLY appear on genuine success. A `forge` PASS on the vulnerable
code is NOT such a signal (an unrelated test passes too); a PASS that then FAILS once
the bug is fixed IS.

### User Story 1 - A PASS that survives the fix is caught, not trusted (Priority: P1) 🎯 MVP

As the operator, when the harness reports a PoC as PASSED, I need it to have proven
that the pass actually depends on the vulnerability — by re-running the same PoC
against a copy of the source with the finding's own fix applied and confirming the
PoC now FAILS. A PoC that still passes after the fix was never exploiting the bug and
must be surfaced as such, not counted as a success.

**Why this priority**: This is the deepest "do we trust a green run" failure mode —
the one that this session's hardest incident (a defect-free PASS unrelated to the
exploit) slipped through, catchable before only by a human reading the code. It is
the whole point of the feature.

**Independent Test**: Drive the harness (via the spec-009 fake-sandbox harness) so a
passing PoC re-runs against patched source: script "fails on patched" → the outcome
is a VERIFIED pass; script "still passes on patched" → the outcome is a distinct
`unverified_pass`. No model, Docker, or network.

**Acceptance Scenarios**:

1. **Given** a PoC that PASSES on the vulnerable code, **When** it is re-run against a
   copy with the finding's fix applied and now FAILS, **Then** the finding's outcome
   is recorded as a verified pass (the exploit is genuinely blocked by the fix).
2. **Given** a PoC that PASSES on the vulnerable code, **When** it is re-run against
   the patched copy and STILL PASSES, **Then** the outcome is downgraded to
   `unverified_pass` — it is not reported as a success.
3. **Given** the mutation-verify pass, **When** it applies the fix, **Then** it does so
   only in an ephemeral copy of the source — the real target tree is never modified.

---

### User Story 2 - The verifier never fabricates a failure it can't substantiate (Priority: P2)

As the operator, I need mutation-verify to degrade honestly: if a finding carries no
machine-applicable fix, or the fix does not apply cleanly to the source, the harness
must NOT downgrade the pass — it records that verification was unavailable (with the
reason) and keeps the existing `passed` outcome. The feature strengthens a PASS when
it can; it never invents a failure it didn't observe.

**Why this priority**: A verifier that false-downgrades a genuine pass whenever it
can't apply a diff would be worse than none — it would erode trust in the harness's
own reports. Honest "unavailable" is the correct degraded state.

**Independent Test**: A finding with no `**Fix**` block, and one whose diff does not
apply to the (fake) source, each produce a `mutation_verify_unavailable` event with a
reason and leave the `passed` outcome unchanged — offline.

**Acceptance Scenarios**:

1. **Given** a passing PoC whose finding has no extractable fix, **When** mutation-verify
   runs, **Then** it logs `mutation_verify_unavailable` (reason: no fix) and keeps
   `passed`.
2. **Given** a passing PoC whose finding's fix diff does not apply to the source,
   **When** mutation-verify runs, **Then** it logs `mutation_verify_unavailable`
   (reason: patch failed) and keeps `passed` — it does not guess or partially apply.

---

### User Story 3 - Evidence from the hardest known case (Priority: P3)

As the operator, I would like to see mutation-verify run against a real finding — but
this is optional and lower priority given Kaggle-quota economics; the offline
scenarios above are the completion bar.

**Why this priority**: Lowest — the mechanism's correctness is proven offline; a live
run is confirmatory, not required, and a "PoC still doesn't converge to a real PASS
to verify" outcome is itself a valid, honest result.

**Independent Test**: If run, apply mutation-verify to a live H-01 PoC that reaches a
PASS and record honestly whether the pass verified, downgraded, or was unavailable,
against [docs/roadmap.md](../../docs/roadmap.md)'s existing H-01 record.

**Acceptance Scenarios**:

1. **Given** a live H-01 run that reaches a PASS, **When** mutation-verify runs,
   **Then** the verified/unverified/unavailable result is recorded honestly — the
   PoC being downgraded to `unverified_pass` is an acceptable, informative outcome.

### Edge Cases

- What happens when the fix diff touches a file the PoC doesn't exercise (a no-op
  patch for this exploit)? → The PoC would still pass on the patched code →
  `unverified_pass`, correctly (the fix that's supposed to block THIS exploit didn't
  change the PoC's result, so the PoC isn't testing that exploit).
- What happens when applying the fix makes the source fail to COMPILE (a malformed or
  partial diff)? → That is not a clean application → `mutation_verify_unavailable`
  (reason: patched source didn't build), never a downgrade.
- What happens when the PoC's own re-run errors for an infrastructure reason (sandbox
  timeout) rather than a test failure? → Treated as unavailable, not as "failed on
  patched" — a downgrade must rest on an actual test FAILURE, not an infra error.
- What happens on a compiled-but-not-passed outcome (path A, `compiled`)? → Mutation-
  verify runs only on a genuine `passed` (real_pass); a `compiled`-only outcome is not
  a success claim to verify and is left untouched.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The harness MUST extract a finding's suggested fix (its inline
  unified-diff block) during task extraction, alongside id/title/location/description,
  when the report provides one.
- **FR-002**: When and only when a PoC reaches a genuine PASS (`real_pass`), the harness
  MUST run a mutation-verify pass: apply the finding's fix to an ephemeral copy of the
  target source and re-run the SAME PoC in the same network-isolated sandbox.
- **FR-003**: If the re-run on the patched source FAILS the PoC's assertion, the pass
  MUST be recorded as verified; if it STILL PASSES, the outcome MUST be downgraded to a
  distinct `unverified_pass`.
- **FR-004**: The real target source tree MUST NOT be modified — the fix is applied
  only to an ephemeral copy used for the verify run.
- **FR-005**: If the finding carries no machine-applicable fix, or the fix does not
  apply cleanly (or the patched source fails to build), the harness MUST log a
  `mutation_verify_unavailable` event with the reason and keep the existing `passed`
  outcome — it MUST NOT downgrade on an inability to verify.
- **FR-006**: A downgrade to `unverified_pass` MUST rest on an actual PoC test FAILURE
  on the patched code, never on an infrastructure error (timeout, sandbox unavailable),
  which is treated as unavailable.
- **FR-007**: Mutation-verify MUST run ONLY post-hoc on an already-passing PoC — it is
  never a precondition for a PoC to be drafted or run, and it never changes the
  draft/fix loop's behavior for non-passing outcomes.
- **FR-008**: The entire mutation-verify orchestration (fix extraction → apply to a
  copy → re-run → compare → classify) MUST be exercisable end-to-end offline through
  the spec-009 fake-model + fake-sandbox integration harness, with no model, Docker, or
  network.
- **FR-009**: Diff application MUST use standard patch tooling; a diff that does not
  apply with standard tooling is a clean `mutation_verify_unavailable`, not an occasion
  for fuzzy/heuristic patching.

### Key Entities

- **Finding fix**: the suggested remediation for a finding — its inline unified-diff
  block from the audit report — carried on the finding alongside id/title/location/
  description.
- **Mutation-verify run**: a post-PASS re-execution of the same PoC against an
  ephemeral copy of the source with the finding fix applied.
- **Verify verdict**: the classification of a mutation-verify run — `verified` (PoC
  fails on patched), `unverified_pass` (PoC still passes on patched), or `unavailable`
  (no fix / patch failed / infra error), each with its own recorded event.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A PoC that passes on the vulnerable code but ALSO passes on the patched
  code is reported as `unverified_pass`, not as a success — 100% of such cases in the
  offline suite (this is the exact class of the 2026-07-06 false positive).
- **SC-002**: A PoC that passes on the vulnerable code and FAILS on the patched code is
  reported as a verified pass — 100% of such cases offline.
- **SC-003**: When no applicable fix exists or the diff won't apply, the harness keeps
  the `passed` outcome and records `mutation_verify_unavailable` — it never downgrades
  a pass it could not actually disprove (0 false downgrades in the offline suite).
- **SC-004**: The real target source tree is byte-for-byte unchanged after any
  mutation-verify run (verified in the offline suite).
- **SC-005**: The full offline test suite (including spec-009's loop harness extended
  with mutation-verify scenarios) passes with no model, Docker, or network.

## Assumptions

- The "operator" runs `scripts/poc_queue_runner.py`; internal tooling reliability work.
- Audit reports carry a machine-readable unified-diff fix per finding when a fix is
  given (confirmed for this session's report — findings include `--- a/… +++ b/… @@`
  blocks). Findings without one degrade to `mutation_verify_unavailable`.
- "The same sandbox" means the existing network-isolated Docker `run_tests` path; the
  mutation-verify run reuses it against the patched source copy, adding no new
  execution surface or privilege.
- Mutation-verify is a post-hoc verifier layered on the existing outcome
  classification; it introduces `unverified_pass` and the `mutation_verify_*` events
  but does not alter any existing non-passing outcome.
- This is step 2 of the harness-review remediation; step 1 (spec 009) landed the
  verdict-logic + loop test coverage and the `_process_finding` extraction this feature
  hooks into and is tested through. Fix GENERATION (when the report has none) and
  Stage 1 scaffold synthesis are separate later specs.
- No secure-kernel change is required or made — confined to the standalone harness and
  its tests.
