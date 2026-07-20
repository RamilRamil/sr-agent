# Feature Specification: Harden Scaffold Synthesis with a Deterministic Repair Pass

**Feature Branch**: `031-harden-scaffold-synth`

**Created**: 2026-07-19

**Status**: Draft

**Input**: User description: "Give scaffold synthesis a bounded deterministic repair pass + an address→interface fix so a synthesized deploy-base compiles instead of being thrown away on the first mechanical error."

## User Scenarios & Testing *(mandatory)*

When the target's shipped deploy base does not deploy a contract a finding needs, the harness
**synthesizes** an extension base that does — and only trusts it if it COMPILES. Today that synthesis
is **one-shot**: it generates the base, compiles a smoke test once, and on any build failure deletes
the base and falls back to the insufficient scaffold. The drafting PoC, by contrast, gets multiple
repair rounds with the harness's deterministic fixers. So a synthesized base dies on a SINGLE
mechanical error the drafting loop would have repaired.

**Motivation (two live GLM-5.2 runs + a deterministic opportunity check).** On the curated eval target, synthesis is
genuinely required — a Level-0 check found 0/5 findings have an alternative existing base (the one
shipped base lacks a cooldown contract 3 of 5 findings need), so no discovery change can avoid
synthesis on this target (spec 030 deferred for that reason). And synthesis is where the live run broke: the
synthesized base failed with `Invalid implicit conversion from address to contract IFoo` — the model
passed `someSetter(address(x))` where the function wants the interface type — a mechanical error the
shared repair hints do not yet cover. Making synthesis reliable is the measurable lever on this target.

### User Story 1 - A synthesized base survives a repairable mechanical error (Priority: P1)

When the smoke build of a synthesized base fails to compile on a mechanical error the harness's
deterministic fixers can repair, synthesis applies those fixers and re-compiles (up to a small bounded
number of rounds) instead of discarding the base immediately.

**Why this priority**: This is the feature — it turns synthesis from one-shot into a bounded repair
loop reusing the machinery the drafting loop already trusts, directly reducing spurious rejections.

**Independent test**: A synthesized base that fails the first smoke build but compiles after a
deterministic fix is ACCEPTED (returned, `scaffold_synthesized` emitted); the smoke build is stubbed
to return not-compiled then compiled; no model call is made. Verified offline.

**Acceptance Scenarios**:

1. **Given** a synthesized base whose first smoke build fails with a deterministically-fixable error and
   whose second build (after the fix) compiles, **When** synthesis runs, **Then** the base is accepted
   and `scaffold_synthesized` is emitted.
2. **Given** a synthesized base that never compiles within the bounded rounds, **When** synthesis runs,
   **Then** it returns nothing (`scaffold_synthesis_failed`, unchanged honest fallback) and no base is
   trusted.
3. **Given** a synthesized base that compiles on the FIRST smoke build, **When** synthesis runs, **Then**
   it is accepted immediately (no repair rounds run) — behavior unchanged from today.

### User Story 2 - The address→interface error is repaired deterministically (Priority: P1)

The harness's shared repair hints gain a deterministic fix for the address↔interface conversion error
(passing `address(x)` where a contract/interface type is required): wrap it as `IFoo(address(x))` /
use the typed variable. Because the hint machinery is shared, this helps both the synthesized base and
the drafting PoC.

**Why this priority**: This is the specific mechanical error the live synthesis hit; without a fix for
it the repair pass of US1 has nothing to apply for the observed failure. Ships with US1.

**Independent test**: Given forge output reporting the address→contract conversion error naming a type
`IFoo`, the repair hints include an authoritative instruction to wrap the argument as `IFoo(address(x))`.
Verified offline over synthetic forge-error fixtures.

**Acceptance Scenarios**:

1. **Given** forge output `Invalid implicit conversion from address to contract IFoo requested`, **When**
   repair hints are built, **Then** they name `IFoo` and instruct wrapping the argument as
   `IFoo(address(...))` (or passing the typed variable).
2. **Given** forge output with no conversion error, **When** repair hints are built, **Then** no
   conversion hint is emitted (the rule is specific, not blanket).

### User Story 3 - The run log shows the repair pass (Priority: P2)

Each synthesis repair round and its outcome (accepted / exhausted) is visible in the run log, along
with which deterministic fixes were applied, so an operator can see why a base was accepted or given up.

**Why this priority**: Attribution for the operator and the eval; the pass works without it.

**Independent test**: When synthesis runs a repair round, an event records the round and the final
accept/give-up. Verified offline.

**Acceptance Scenarios**:

1. **Given** a synthesized base repaired over one or more rounds, **When** it is accepted, **Then** the
   log shows the repair round(s) and the `scaffold_synthesized` accept.
2. **Given** the bounded rounds are exhausted, **When** synthesis gives up, **Then** the log shows the
   attempts and the `scaffold_synthesis_failed` give-up (reason unchanged).

### Edge Cases

- **Non-repairable error** (e.g. the base calls an INVENTED function that does not exist): no
  deterministic fix applies; the base is rejected after the bounded rounds — the invented-API class is
  explicitly out of scope and still falls through to the honest fallback.
- **Fixers make no change**: if a repair round produces no textual change to the base, the pass stops
  early (no point recompiling identical source) and gives up — no wasted smoke builds.
- **Infra failure during a repair build** (sandbox unavailable / timeout): treated as today's `infra`
  outcome, not a code failure; the base is discarded without falsely blaming its source.
- **Acceptance bar unchanged**: a base is trusted ONLY if it actually compiles (feature 011 FR-004); the
  repair pass never lowers this bar — it only gives more chances to REACH it.
- **Writes stay in the untracked audit area**: repair rewrites the synthesized base file in place under
  the untracked audit area; tracked source is never touched.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When a synthesized base's smoke build does not compile, synthesis MUST apply the harness's
  existing deterministic fixers to the base source and re-compile, up to a small fixed bounded number of
  rounds, before giving up.
- **FR-002**: The repair pass MUST reuse the deterministic fixers the drafting loop already trusts
  (import-path repair + the shared targeted-hint fixes resolved against the real API/symbol index) and
  MUST NOT make any model call.
- **FR-003**: Synthesis MUST accept the base the moment a smoke build compiles (no further rounds), and
  MUST return the current honest failure only after the bounded rounds are exhausted.
- **FR-004**: The shared repair hints MUST gain a deterministic rule for the address↔interface
  conversion error: when solc reports an invalid implicit conversion from address to a contract/interface
  type, emit an authoritative instruction to wrap the argument as `<Type>(address(x))` (or pass the
  typed variable), keyed off the real type name in the error.
- **FR-005**: The conversion rule MUST be specific — emitted only when the conversion error is present,
  never as blanket advice — and MUST benefit both the synthesized base and the drafting PoC (shared hints).
- **FR-006**: Synthesis MUST emit events recording each repair round, which deterministic fixes were
  applied, and the final outcome (accepted `scaffold_synthesized` / exhausted `scaffold_synthesis_failed`).
- **FR-007**: A repair round that produces no change to the base source MUST stop the pass early (no
  redundant recompile).
- **FR-008**: The smoke-compile ACCEPTANCE bar MUST be unchanged — a base is trusted only if it actually
  compiles; the repair pass MUST NOT lower this bar.
- **FR-009**: Synthesis MUST continue to write only under the untracked audit area and MUST NEVER mutate
  tracked source; repair rewrites the synthesized base file in place there.
- **FR-010**: The change MUST be confined to `synthesize_scaffold`'s repair pass and the shared repair
  hints. The drafting/repair loop, the 029 trace feedback, scaffold discovery/selection, the fork oracle,
  the anti-cheat gate, and falsification MUST be untouched.
- **FR-011**: The invented-API class (a base calling a function that does not exist) is out of scope —
  it is not deterministically fixable, and such bases still fall through to the honest failure.
- **FR-012**: Behavior MUST be validated offline with deterministic tests over SYNTHETIC fixtures
  (invented contract/interface names, captured-bad-synth-base source, synthetic forge errors). The model
  call and the forge subprocess MUST NEVER run in tests (stubbed). No real target material enters the
  repo (guarded by `test_no_target_material.py`).

### Key Entities *(include if feature involves data)*

- **Synthesized base**: the model-generated abstract deploy-base written under the untracked audit area.
  The subject of the repair pass; rewritten in place across rounds.
- **Repair round**: one iteration of (apply deterministic fixers → re-run the smoke compile). Bounded by
  a small fixed count. Records the fixes applied and the compile result.
- **Deterministic fixer**: an existing mechanical repair (import-path depth, targeted authoritative
  fixes incl. the new address→interface rule) applied to the base source without any model call.
- **Address→interface rule**: the new deterministic targeted hint keyed on the solc conversion error,
  naming the real type and prescribing `<Type>(address(x))`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A synthesized base that fails once then compiles after a deterministic fix is accepted by
  the repair pass (verified with the smoke build stubbed no-build→compiled; no model call).
- **SC-002**: A base that never compiles within the bounded rounds is still rejected (honest fallback
  unchanged) — verified.
- **SC-003**: A base that compiles on the first smoke build is accepted with zero repair rounds
  (behavior unchanged) — verified.
- **SC-004**: The address→interface conversion rule emits the correct `<Type>(address(x))` instruction
  for a synthetic conversion error and stays silent when the error is absent — verified.
- **SC-005**: The repair pass makes no model call (verified by a model stub that fails if invoked).
- **SC-006**: The full offline test suite passes with no model/forge/network access, and
  `test_no_target_material.py` passes.
- **SC-007**: The drafting loop, scaffold discovery, the fork oracle, `_poc_defects`, and
  `mutation_verify` are unchanged (their existing tests still pass).
- **SC-008** (live corroboration, operator step — not a unit test): after the change, synthesis emits
  `scaffold_synthesized` (compiles) on the eval findings that genuinely need it, measured as a
  synth-compile success count contrasted with the pre-change one-shot rejection.

## Assumptions

- The deterministic fixers the drafting loop uses (import-path repair, targeted authoritative hints) are
  applicable to the synthesized base source as-is — the base is ordinary Solidity, the same shape the
  fixers already handle for PoCs.
- A small fixed round bound (e.g. 2–3) is adequate to clear the mechanical errors synthesis realistically
  hits; the exact bound is an implementation detail set in the plan. No operator flag is required.
- The address→interface conversion error text is stable enough to key a deterministic rule on (the real
  type name appears in the message); other conversion variants are best-effort.
- Reusing the smoke-compile as the repair oracle is acceptable cost — each round is one smoke build (the
  same cost profile as today's single build), bounded by the round count; the deterministic-only pass
  adds no model calls.

## Out of Scope

- A MODEL-driven synthesis repair loop (extra model calls / cost) — the repair here is deterministic only.
- Fixing invented-API / non-existent-function calls in the synthesized base.
- The finding-aware scaffold discovery of spec 030 (deferred — no opportunity on the current target).
- The drafting/repair loop itself and the spec-029 trace feedback.
- The noisy method-fragment issue in the finding's needed-types derivation (a separate small fix; it
  inflates missing-types but does not change that synthesis is genuinely needed here).
- The fork oracle, `_poc_defects`, and `mutation_verify`.
- Model selection / paid-vs-local strategy and any Constitution Principle V matter (this is a
  deterministic change, model-agnostic).
