# Feature Specification: Stage 1 Scaffold Synthesis

**Feature Branch**: `011-scaffold-synthesis`

**Created**: 2026-07-10

**Status**: Draft

**Input**: User description: "Stage 1 scaffold synthesis for the PoC-workability harness. This session's single hardest blocker on H-01 was that the auto-discovered scaffold (`StrataProtocolDeploymentBase`) deploys `ERC20Cooldown` but never declares/deploys the `SharesCooldown` the finding needs; the model wrote a mechanistically-correct exploit that failed only on `sharesCooldown` being undeclared, six live attempts burned before a human noticed. Spec 009 US3 DETECTS this (`scaffold_missing_types`), but detection only tells the operator to hand-write a deploy base. This feature closes the loop: when the scaffold is insufficient, SYNTHESIZE a deploy-base that declares and deploys the missing contract, using the harness's configured model given the missing contract's real source; VALIDATE it compiles in the sandbox before trusting it; use it on success, fall back honestly on failure. Offline-validate the orchestration via spec-009's fake harness; live H-01 optional. Out of scope: synthesizing when the auto-scaffold is sufficient; making synthesis mandatory; a paid-API dependency; kernel changes; a general scaffold-generation framework; guaranteeing semantic perfection (compile-validation is the bar; spec 010 mutation-verify remains the correctness check). Step 3 of the harness-review remediation."

## User Scenarios & Testing *(mandatory)*

The "user" is the SR-agent **operator/maintainer** of the PoC-workability harness —
internal capability work. It follows the eval-robustness doctrine of
[docs/eval-principles.md](../../docs/eval-principles.md): a synthesized scaffold is
trusted only on a positive signal (it actually compiles), never assumed.

### User Story 1 - A missing deploy-base is synthesized, not left to a human (Priority: P1) 🎯 MVP

As the operator, when the harness detects that a finding's auto-discovered scaffold
cannot deploy the contract the finding needs, I want the harness to synthesize a
deploy-base that declares and deploys that contract — so a finding is not dead on
arrival just because no hand-written base for it exists, without me having to write
one by hand.

**Why this priority**: This is the one structural blocker that no amount of better
grounding could overcome — the model wrote a correct H-01 exploit that failed only
because the scaffold never declared `sharesCooldown`. Closing this loop is the whole
point.

**Independent Test**: Feed the harness a finding whose auto-scaffold is detected
insufficient (missing a needed contract type) and a scripted model that returns a
synthesized deploy-base; confirm the harness uses the synthesized base for drafting
instead of the insufficient one — no live model needed.

**Acceptance Scenarios**:

1. **Given** a finding whose auto-discovered scaffold does not declare/deploy a
   contract type the finding needs, **When** the harness processes it, **Then** it
   invokes scaffold synthesis for the missing type(s) before drafting.
2. **Given** a synthesized deploy-base that declares and deploys the missing contract,
   **When** synthesis succeeds and validates, **Then** the finding's draft/fix loop
   uses the synthesized base (so the model can inherit it and reference the now-declared
   contract).

---

### User Story 2 - A synthesized scaffold is trusted only if it compiles (Priority: P1)

As the operator, I need a synthesized scaffold to be validated by actually compiling
it in the sandbox before it is used — a scaffold that does not build is worse than
none (it would fail every draft on the scaffold's own error), so it must be discarded
and the run must fall back honestly.

**Why this priority**: Same eval-robustness discipline as specs 006/010 — never trust
generated code on assertion; a positive compile signal is the bar. An unvalidated bad
scaffold would poison every attempt for that finding.

**Independent Test**: Script the sandbox to report the synthesized scaffold as
NOT compiling; confirm the harness discards it, logs a `scaffold_synthesis_failed`
event with a reason, and falls back to the existing (insufficient) behavior without
blocking the run — offline.

**Acceptance Scenarios**:

1. **Given** a synthesized scaffold that compiles in the sandbox, **When** it is
   validated, **Then** it is accepted and used for drafting.
2. **Given** a synthesized scaffold that does NOT compile, **When** it is validated,
   **Then** it is discarded, `scaffold_synthesis_failed` is logged with the reason,
   and the finding proceeds under the prior (insufficient-scaffold) behavior — the run
   is never blocked and no non-compiling scaffold is ever used.
3. **Given** the model declines or fails to produce a scaffold at all, **When**
   synthesis is attempted, **Then** the same honest fallback applies.

---

### User Story 3 - Evidence: does a synthesized base finally unblock H-01 (Priority: P3)

As the operator, I would like to see whether a synthesized `SharesCooldown` deploy-base
lets H-01 finally reach a real, mutation-verified PASS — the ultimate end-to-end proof
that this whole remediation arc worked — but this is optional and not a completion
condition.

**Why this priority**: Lowest — the mechanism's correctness is proven offline; a live
end-to-end is confirmatory, and given Kaggle economics it is a nice-to-have. A
still-not-converged result is a valid, honest outcome.

**Independent Test**: If run, a live H-01 pass through synthesis → drafting →
(spec 010) mutation-verify, recorded honestly in `docs/roadmap.md` — including whether
the synthesized base compiled, whether H-01 then reached a PASS, and whether that PASS
was mutation-verified or downgraded.

**Acceptance Scenarios**:

1. **Given** a live H-01 run where the auto-scaffold is insufficient, **When**
   synthesis runs, **Then** the outcome (synthesized base compiled? H-01 reached PASS?
   mutation-verified?) is recorded honestly — a non-convergence is acceptable.

### Edge Cases

- What happens when synthesis is needed for MORE than one missing contract type? → The
  synthesized base should declare/deploy all detected missing types, or, if that's not
  feasible in one base, the harness handles it as a synthesis that either covers them
  or falls back honestly — it never silently covers only some and claims success.
- What happens when the synthesized scaffold compiles but the model then still can't
  use it (a naming mismatch)? → Out of this feature's bar (compile-validation is the
  gate); a resulting PASS is still subject to spec 010 mutation-verify, and a
  non-PASS is handled by the existing draft/fix loop.
- What happens when the auto-scaffold is already sufficient? → Synthesis never fires
  (only on detected insufficiency) — the common path is untouched.
- What happens when validating the synthesized scaffold errors for an infrastructure
  reason (sandbox timeout) rather than a compile failure? → Treated as a synthesis
  failure (honest fallback), never as "validated".
- Where does a synthesized scaffold live? → In an ephemeral/audit scaffold area that
  never pollutes the target project's tracked source; it is the harness's own
  generated infrastructure (production-mode input), consistent with the operator-
  supplied scaffold convention already in the harness.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When `scaffold_missing_types` reports a non-empty set of missing contract
  types for a finding, the harness MUST attempt to synthesize a deploy-base that
  declares and deploys those type(s) — and MUST NOT attempt synthesis when the
  auto-discovered scaffold is already sufficient.
- **FR-002**: Synthesis MUST use the harness's already-configured model (the same
  local/tunnel model the harness uses for drafting) — it MUST NOT introduce a new
  paid-API/Claude dependency into the standalone harness.
- **FR-003**: Synthesis MUST be grounded in the missing contract type(s)' real source
  and the existing auto-discovered scaffold as a structural pattern, and MUST produce a
  base that (a) inherits the existing base, (b) declares the missing contract as a
  state variable, (c) deploys/wires it in a setup helper.
- **FR-004**: A synthesized scaffold MUST be validated by compiling it in the same
  network-isolated sandbox before use; a scaffold that does not compile MUST be
  discarded and MUST NEVER be used for drafting.
- **FR-005**: On successful synthesis+validation, the finding's draft/fix loop MUST use
  the synthesized scaffold; on any failure (won't compile, model won't produce one,
  or an infra error during validation), the harness MUST log a `scaffold_synthesis_failed`
  event with a reason and fall back to the prior insufficient-scaffold behavior —
  the run is never blocked.
- **FR-006**: A synthesized scaffold MUST live in an ephemeral/audit scaffold area and
  MUST NOT modify the target project's tracked source.
- **FR-007**: The whole orchestration (detect insufficiency → synthesize → validate →
  use-or-fallback) MUST be exercisable end-to-end offline through the spec-009 fake-model
  + fake-sandbox harness, with no model, Docker, or network.
- **FR-008**: Any PASS produced under a synthesized scaffold MUST still be subject to
  the spec-010 mutation-verify gate — synthesis changes how a PoC is set up, never what
  counts as a trustworthy pass.

### Key Entities

- **Missing type set**: the contract type name(s) a finding needs that the
  auto-discovered scaffold does not declare/deploy (from `scaffold_missing_types`,
  spec 009).
- **Synthesized deploy-base**: a generated Foundry abstract contract that inherits the
  existing base and declares+deploys the missing contract(s), living in the harness's
  ephemeral/audit scaffold area.
- **Synthesis verdict**: `synthesized` (produced and compiled → used) or `failed`
  (no output / won't compile / infra error → honest fallback), each with its own event.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A finding whose auto-scaffold is insufficient triggers synthesis, and a
  synthesized base that compiles is used for that finding's drafting — verified offline.
- **SC-002**: A synthesized scaffold that does NOT compile is discarded 100% of the
  time and never used for drafting — the harness falls back honestly with a logged
  reason (0 uses of a non-compiling scaffold in the offline suite).
- **SC-003**: A finding whose auto-scaffold is already sufficient never triggers
  synthesis — the common path is measurably untouched.
- **SC-004**: The target project's tracked source is byte-for-byte unchanged after any
  synthesis run (all generated scaffolding lives in the ephemeral/audit area).
- **SC-005**: The full offline suite passes with the synthesis scenarios added — no
  model, Docker, or network; no bug-bounty target code embedded in tests.
- **SC-006** (optional, only if live-validated): A live H-01 run's synthesis outcome is
  recorded honestly — whether the synthesized base compiled, whether H-01 reached a
  PASS, and whether that PASS was mutation-verified (spec 010) — with non-convergence an
  acceptable result.

## Assumptions

- The "operator" runs `scripts/poc_queue_runner.py`; internal capability work.
- The harness's configured model (via `--model`/`--host`) is capable enough to draft a
  deploy-base given the real contract source; a more capable model can be pointed at it
  through those existing flags — no new dependency (constitution V).
- A synthesized scaffold is the harness's own generated infrastructure — an acceptable
  "production-mode" input, the same framing under which operator-supplied
  `--test-scaffold` bases are already accepted; it is not part of the honest
  "from-original-code-only" experiment and is clearly logged as synthesized.
- Compile-validation is the trust bar this feature enforces; semantic correctness of a
  resulting PASS remains the job of spec 010's mutation-verify gate (FR-008).
- This is step 3 of the harness-review remediation; it depends on spec 009's
  `scaffold_missing_types` (detection) and `_process_finding` (the loop hook), and
  complements spec 010. Fix GENERATION (010) and prompt management are separate.
- No secure-kernel change is required or made — confined to the standalone harness and
  its tests.
