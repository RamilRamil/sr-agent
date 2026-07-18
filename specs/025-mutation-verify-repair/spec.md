# Feature Specification: Make Falsification-Verification Actually Run

**Feature Branch**: `025-mutation-verify-repair`

**Created**: 2026-07-16

**Status**: Draft

**Input**: User description: "Make mutation-verification actually run, and stop reporting unverified passes as verified. The report's fix diffs are illustrative, not applyable patches, so the project's central trust mechanism has never once executed. Part 1: split the outcome so a verified pass and a never-verifiable pass stop reading identically. Part 2: deterministically reconstruct an applyable patch from an illustrative diff — verbatim-match-or-refuse, no model, offline."

## Context: what the live evidence shows

The project's trust rule is that a passing proof is not evidence until the SAME proof **fails** once the finding's own fix is applied. That falsification step is the only thing separating a proof from a test that happens to be green — the lesson the project learned when a defect-free, passing proof turned out to be testing something unrelated to the bug.

**That step has run successfully zero times.** Across two live runs and 10 `passed` verdicts:

| run | falsification outcomes |
|---|---|
| A | `patch_failed`, `patch_failed`, `no_fix` |
| B | `no_fix` × 8 |

The cause was proved with the real tools rather than inferred. The report's fix blocks are **illustrative**, not machine-applicable: they carry correct source-file headers, but their hunk markers are prose context (`@@ struct TRequest {`, `@@ function cancel(...) external onlyUser(user) {`) with **no line numbers**. Both standard patch tools reject them outright — one with "No valid patches in input", the other with "I can't seem to find a patch in there anywhere".

This is normal audit-report style, not a defective report. So the mechanism's founding assumption — *the report carries an applyable fix* — is false in general, and the existing "never fuzzy-patch; a diff neither tool applies is a clean failure" rule guaranteed the mechanism would be a **permanent no-op on real reports**. It was not broken by a bug; it could never have worked.

Compounding this, an inability to verify never downgrades a pass (correctly — see FR-006), and the reported outcome does not record the difference. So `passed` currently reads identically whether the proof survived falsification or was never testable at all.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An operator can tell a verified proof from an unverified one (Priority: P1)

The operator reads the run's results and can immediately see, per finding, whether the proof was falsification-tested and survived, or whether verification never happened — and why (no fix in the report, the fix could not be reconstructed, the patched source did not build, an infrastructure error). Today both appear as the same word, so a run reporting eight passes silently mixes "proved" with "never checked".

**Why this priority**: This is the honesty fix, and it is independent of everything else. Even if no fix source ever lands (US2, US3), this stops the tool from overstating what it knows — which it has been doing on every run to date, including in reports written to the operator. It is also by far the cheapest of the four.

**Independent Test**: Run the pipeline over a finding whose fix is absent and one whose fix verifies; the two results are distinguishable in the reported outcome, and the reason is stated for the unverified one.

**Acceptance Scenarios**:

1. **Given** a proof that passes and whose falsification step ran and failed the patched build test (i.e. the proof depends on the bug), **When** the result is reported, **Then** it is marked as a verified pass.
2. **Given** a proof that passes but whose falsification step could not run, **When** the result is reported, **Then** it is marked as an unverified pass, distinct from a verified one, and carries the reason it could not run.
3. **Given** a proof that passes but still passes after the fix is applied, **When** the result is reported, **Then** it is reported as the existing "the proof did not depend on the bug" downgrade — unchanged by this feature.
4. **Given** any inability to verify, **When** the result is reported, **Then** the pass is NEVER downgraded to a failure — inability to check is not evidence of a defect.

---

### User Story 2 - The operator can supply the fix directly (Priority: P1)

For any finding, the operator can hand the system a real patch file and have falsification run against it. Their patch takes precedence over anything the report contains. Nothing needs reconstructing — it is already a genuine patch — so it applies with standard tooling as-is.

**Why this priority**: this is what removes the ceiling. The report carries a fix for a minority of findings; the operator can write one for **any** of them, and a human-authored fix is the highest-trust source available — deterministic, no model, and squarely within the project's human-authority principle. Crucially, the fix does not need to be production-quality: falsification only requires that the bug's behavior is gone, so inverting a condition or hard-failing the vulnerable branch is sufficient and takes minutes.

This matters most where it is least obvious. The majority of tasks in a real run are **leads** — hypotheses, not confirmed findings — and there a passing proof is the *only* evidence the lead is real. An unverified pass on a lead is the most dangerous self-deception this pipeline can produce, and leads never carry a report fix.

**Independent Test**: Point the system at a synthetic finding with no fix in the report, supply a patch file, and falsification runs and reports verified/unverified on its merits.

**Acceptance Scenarios**:

1. **Given** a finding with no fix in the report and an operator-supplied patch, **When** the proof passes, **Then** falsification runs against that patch and the result is reported as verified or as the did-not-depend-on-the-bug downgrade.
2. **Given** a finding that has BOTH a report fix and an operator-supplied patch, **When** falsification runs, **Then** the operator's patch is used — the human is the higher authority.
3. **Given** an operator-supplied patch that does not apply to the target, **When** falsification is attempted, **Then** it is refused with that reason and reported as an unverified pass — never as verified, never as a failure.
4. **Given** no operator patch and no report fix, **When** the proof passes, **Then** it is reported as an unverified pass with reason "no fix available" — the honest floor.

---

### User Story 3 - An illustrative fix becomes a real, applyable patch (Priority: P1)

When a report carries an illustrative fix block, the system reconstructs a genuine patch from it — locating each hunk's anchor in the real source, confirming every context and removal line matches that source exactly, and emitting a patch with correct line numbers that standard tooling applies. The falsification step then runs for real, and a proof that survives it is finally worth the word "verified".

**Why this priority**: it makes the report's own fixes usable at zero marginal cost to the operator — for the minority of findings that carry one, verification becomes free. It is the cheap complement to US2's unlimited-but-manual channel, not a substitute for it.

**Independent Test**: Give the system a synthetic illustrative fix whose anchors and context match a synthetic source; it produces a patch that standard tooling applies cleanly, and the falsification step runs.

**Acceptance Scenarios**:

1. **Given** an illustrative fix whose anchor matches exactly one place in the real source and whose context and removal lines match that source verbatim, **When** it is reconstructed, **Then** the result is a patch that standard tooling applies cleanly, and verification proceeds.
2. **Given** an illustrative fix whose removal lines carry deep source indentation, **When** it is reconstructed, **Then** the indentation is preserved exactly and the patch still applies.
3. **Given** an illustrative fix consisting of removals and additions with no trailing context, **When** it is reconstructed, **Then** it still produces an applying patch.
4. **Given** a fix block spanning multiple hunks in one file, **When** it is reconstructed, **Then** every hunk is located independently and the combined patch applies.

---

### User Story 4 - Reconstruction refuses rather than guesses (Priority: P1)

When anything about the reconstruction is uncertain — the anchor cannot be found, it matches more than one place, or a context or removal line does not match the source — the system refuses, says why, and reports the finding as unverified. It never fuzzy-matches, never picks a "best" location, and never applies a patch it is not certain of.

**Why this priority**: This is the load-bearing safety property. A patch applied to the wrong place produces a **wrong** verified/unverified signal — actively worse than no signal, because the operator would trust it. The project's standing discipline (a conservative gate that under-reports beats a permissive one that inflates) applies with full force here: this mechanism exists to be the thing you can trust when the model cannot be.

**Independent Test**: Feed anchors that are abbreviated, absent, or ambiguous, and a context line that does not match; each is refused with a stated reason and reported as unverified, never as verified.

**Acceptance Scenarios**:

1. **Given** an anchor abbreviated by the report's author (e.g. an elided parameter list) so it matches nothing verbatim in the source, **When** reconstruction is attempted, **Then** it refuses with a stated reason and the finding is reported unverified.
2. **Given** an anchor that matches more than one location in the source, **When** reconstruction is attempted, **Then** it refuses as ambiguous rather than choosing one.
3. **Given** a context or removal line that does not match the source verbatim, **When** reconstruction is attempted, **Then** it refuses.
4. **Given** any refusal, **When** the result is reported, **Then** the outcome is an unverified pass with the reason — never a verified pass, and never a failure.

---

### Edge Cases

- The report contains no fix for a finding at all → unverified with reason "no fix"; this is a report-content limit, not an error, and no amount of engineering can change it.
- The reconstructed patch applies, but the patched source does not build → unverified with reason "patched source did not build" (existing behavior, now visible in the outcome).
- The anchor matches exactly one line, but the hunk's context lines match at a different place than the anchor → refuse; agreement between anchor and context is required.
- Removal and addition lines are identical except for a middle line, with no trailing context → must still reconstruct (observed in a real block).
- An illustrative fix names a file that does not exist in the target → refuse with reason.
- A fix block spans multiple files → each file's hunks are located in that file; any refusal in any hunk refuses the whole fix (a partially-applied fix would be a wrong signal).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The reported outcome for a passing proof MUST distinguish a falsification-verified pass from a pass whose verification could not run.
- **FR-002**: An unverified pass MUST carry the reason verification did not happen, at minimum distinguishing: no fix available from any source, fix could not be reconstructed, patch did not apply, patched source did not build, and infrastructure/execution error.
- **FR-003**: The existing downgrade for a proof that still passes after the fix is applied MUST be preserved unchanged.
- **FR-004**: The system MUST accept an operator-supplied patch for any finding, from outside the agent's own project area, and use it for falsification as-is (it is already a genuine patch and MUST NOT be reconstructed or rewritten).
- **FR-005**: When both an operator-supplied patch and a report fix exist for a finding, the operator's patch MUST take precedence.
- **FR-006**: An operator-supplied patch that does not apply MUST be refused with that reason and reported as an unverified pass — never as verified, and never as a failure.
- **FR-007**: The system MUST reconstruct an applyable patch from an illustrative fix block: resolving the target file from the block's headers, splitting the body at each context marker, locating each marker's anchor in the real source, and emitting a patch with correct line numbers that standard tooling applies.
- **FR-008**: Reconstruction MUST require that the anchor resolves to EXACTLY ONE location in the real source, and that every context and removal line matches that source VERBATIM, including leading whitespace.
- **FR-009**: On anchor-not-found, anchor-ambiguous, context mismatch, missing file, or any other uncertainty, reconstruction MUST refuse with a stated reason; an inability to verify MUST NEVER downgrade a genuine pass to a failure, and MUST NEVER be reported as verified.
- **FR-010**: Reconstruction MUST NOT fuzzy-match, approximate, re-indent, or select a best-guess location under any circumstance.
- **FR-011**: Every fix source MUST be deterministic and run offline with NO model call anywhere in the verification path.
- **FR-012**: If any hunk of a fix refuses, the entire fix MUST be refused — a partially applied fix MUST NOT be used for verification.
- **FR-013**: The system MUST NOT change what counts as a compiled or genuinely passing proof; the compile check, the structural-defect gate, and the fork execution are untouched.
- **FR-014**: The falsification execution step MUST remain unchanged: work on an ephemeral copy, re-run the SAME proof, and never mutate the real target tree.
- **FR-015**: Operator-supplied patches MUST live outside the agent's project area and MUST NOT be committed with the agent (they are target-specific material).
- **FR-016**: The behavior MUST be validated by offline, deterministic tests over SYNTHETIC fixtures (invented names and paths only): an operator patch used and preferred over a report fix, an operator patch that fails to apply, successful reconstruction for an exact anchor, for deep-indentation removals, for a no-trailing-context block, and for a multi-hunk block; refusal for an abbreviated anchor, an absent anchor, an ambiguous anchor, and a mismatched context line. Tests MUST assert the patch is accepted by the real patch tooling, not merely that a string was produced.

### Key Entities

- **Fix source**: where a falsification patch comes from — the operator (any finding, highest authority) or the report's illustrative block (a minority of findings). There is no third source.
- **Illustrative fix block**: the report's human-readable fix — real file headers, prose context markers instead of line numbers. The input to reconstruction.
- **Anchor**: the source line named by a context marker; must resolve to exactly one place or the fix is refused.
- **Reconstructed patch**: a genuine line-numbered patch that standard tooling accepts. The output.
- **Verification outcome**: verified, unverified (with reason), or the existing did-not-depend-on-the-bug downgrade.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any passing proof, an operator can tell from the reported outcome alone whether falsification ran, and if it did not, why — 100% of the time.
- **SC-002**: An illustrative fix whose anchors and context match the source produces a patch accepted by standard patch tooling, and falsification runs — where today the rate is 0 of 10.
- **SC-003**: In 100% of defined uncertainty cases (abbreviated, absent, or ambiguous anchor; mismatched context), reconstruction refuses and the finding is reported unverified — never verified, never failed.
- **SC-004**: Any finding — including one with no fix anywhere in the report, and including a lead — can be falsification-verified once the operator supplies a patch; the reachable set is bounded by operator effort, not by report content.
- **SC-005**: Where both an operator patch and a report fix exist, the operator's is used, 100% of the time.
- **SC-006**: No inability to verify ever turns a genuine pass into a reported failure, in 100% of cases.
- **SC-007**: Verification involves no model, and the offline test suite passes with no model, container, or network.
- **SC-008**: Reconstruction is deterministic: identical input yields an identical patch across runs.

## Assumptions

- Illustrative fix blocks reliably carry correct source-file headers; only the hunk markers lack line numbers. (Observed across every real block available.)
- An anchor is a real source line when the report's author did not abbreviate it. Where they did, no deterministic rule can recover the original, so refusal is the only honest answer — a human can always supply a real patch instead.
- Verbatim matching (whitespace included) is the correct bar. Reports quote source directly, so a mismatch signals either a stale report or a wrong location — both of which must refuse rather than proceed.
- Under-firing is acceptable and expected; misfiring is not. A refused reconstruction costs one unverified label. A wrong one costs the trustworthiness of the entire mechanism.

## Honest expectations (deliberately not oversold)

- **The report channel has a low ceiling.** The available report carries fix blocks for **3 of its 5 findings and none of its 18 leads**, so even flawless reconstruction (US3) makes at most 3 of 23 tasks verifiable — and one of those 3 has an abbreviated anchor and is expected to REFUSE by design. Reconstruction is worth doing (it is free per finding once built), but it is not the answer.
- **The ceiling is a property of the report, not of the mechanism.** The falsification invariant needs *a* fix, not *the report's* fix. The operator channel (US2) applies to any finding, which is what actually removes the limit. An earlier framing of this spec claimed findings without a report diff were "unverifiable forever" — that was wrong, and it was wrong because it mistook one source of fixes for the only one.
- **The bar for an operator fix is low.** Falsification only requires that the bug's behavior is gone — inverting a condition or hard-failing the vulnerable branch is enough. It need not be the fix that ships.
- **Leads are where this matters most.** 18 of 23 tasks in a real run are leads: hypotheses whose passing proof is the *only* evidence they are real, and which never carry a report fix. An unverified pass on a lead is the most dangerous output this pipeline can produce, and only US2 can reach them.
- **US1 is what makes the remainder truthful.** Whatever is not verified must say so, and say why. That is the floor this feature guarantees regardless of how the other stories land.
- A previously-recorded milestone ("real fork-verified proofs") was stronger than the evidence: those proofs ran on a fork, but none survived falsification, because falsification never ran.

## Revisiting the existing no-fuzzy-patching rule

The existing rule states: apply with standard tooling; a diff that neither tool applies is a clean failure, and no fuzzy patching. That rule was written about **applying a real patch** — and it is correct there: fuzzily applying a genuine patch risks silently landing it in the wrong place.

This feature does something different: it **reconstructs a patch from an illustration** and then applies it with standard tooling, unchanged. The reconstruction itself is not fuzzy — FR-005/FR-007 make it stricter than the tools would be, requiring a unique anchor and verbatim context. The rule's intent (never land a fix somewhere we are not certain of) is preserved and, if anything, tightened.

This is recorded here as a deliberate, justified narrowing of that rule rather than a quiet bypass. Its spirit is unchanged: certainty or refusal.

## Out of Scope

- Any model call anywhere in the verification path. A model in this path would destroy the mechanism's purpose — it exists precisely to be trustworthy when the model is not. (Same reasoning that rejected model-as-judge for the discovery benchmark.)
- Changing what counts as a compiled or genuinely passing proof.
- Changing the falsification execution step (ephemeral copy, same proof re-run, real target tree never mutated).
- Deriving a fix automatically when neither the operator nor the report supplies one. A model is disqualified (above). Mechanically mutating the finding's named location was considered and rejected: it tests sensitivity to a *place*, not dependence on the *bug*, so it would manufacture false confidence — the exact failure this mechanism exists to prevent. With no fix from any source, "unverified, no fix available" is the honest and final answer.
- The separate regression observed in run B (two findings that passed in run A failed in run B). One run cannot distinguish a regression from run-to-run variance; it needs its own investigation.
- Mutation testing that synthesizes its own fixes rather than using the report's.
