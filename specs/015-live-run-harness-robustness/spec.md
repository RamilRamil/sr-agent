# Feature Specification: Live-Run Harness Robustness

**Feature Branch**: `015-live-run-harness-robustness`

**Created**: 2026-07-14

**Status**: Draft

**Input**: User description: "Three robustness gaps the first live H-01 run (qwen3-coder:30b
+ the spec-014 knowledge loop) surfaced: (1) prose-wrapped model output is written verbatim
into the PoC file (and tool-mode yields an empty file); (2) a resolved struct/enum lookup
doesn't surface the type's fields, so the model invents them; (3) the lesson-capture trigger
fires on any error-signature change, capturing a false-positive lesson on a regression.
Harness-only hardening, offline-testable, no change to security invariants."

## User Scenarios & Testing *(mandatory)*

The "user" is the SR-agent **maintainer/operator** running the PoC-workability harness
against a real target. These three fixes were each observed in a live run; they make the
harness robust to what the local model actually emits and stop the experiential-knowledge
loop from capturing garbage. None changes a security invariant.

### User Story 1 - The written PoC is always clean Solidity (Priority: P1) 🎯 MVP

As the operator, I need the harness to write **only real Solidity** to the PoC file — never
the model's surrounding explanation, and never an empty file — because the local model wraps
its code in chain-of-thought prose (which lands verbatim in the `.sol` and fails to compile
with a spurious syntax error) or, in tool-calling mode, returns no code at all (producing an
empty test that "passes" vacuously).

**Why this priority**: This corrupts the artifact under test on every affected attempt, so
the whole draft→compile→fix loop is judging garbage. It is the highest-leverage fix — it
alone turns wasted attempts into real ones and also prevents the vacuous-pass false success.

**Independent Test**: Feed the harness a scripted model reply that prepends prose before a
fenced Solidity block (and one that is prose-only) — confirm the written PoC is exactly the
Solidity source (no prose, no fences), and that a reply containing no Solidity is treated as
a failed draft/fix (no empty/prose file written), with a tool-mode reply that yields no code
falling back to the marker protocol.

**Acceptance Scenarios**:

1. **Given** a model reply that begins with explanatory prose then a fenced Solidity block,
   **When** the harness extracts the code, **Then** the written PoC is exactly the Solidity
   source — leading prose and fence markers removed.
2. **Given** a model reply that is prose-only (no Solidity token anywhere), **When** the
   harness extracts the code, **Then** it is treated as a failed draft/fix and **no** empty
   or prose-only PoC file is written.
3. **Given** a tool-calling-mode round-trip that returns no Solidity, **When** it happens,
   **Then** the harness falls back to the marker protocol for that finding rather than
   emitting an empty file.
4. **Given** a reply whose Solidity is followed by trailing prose or a closing fence,
   **When** the harness extracts the code, **Then** the trailing non-Solidity is removed.

---

### User Story 2 - Struct/enum fields are grounded up front, before the model guesses (Priority: P1)

As the operator, I need the struct/enum types referenced by the functions the model is told
to call (the `callable_api` grounding) to have their **full member list** (field names +
types, one level of nesting) shown **in the draft prompt itself** — so the model constructs
them with the right fields instead of inventing them and only discovering the truth several
attempts later.

**Why this priority**: Struct-field blindness is a direct, repeatable cause of
non-compiling PoCs (observed: the model built a 3-field `TExitUpperBounds` that actually has
5 — `p0, p1, TExitParams r0/r1/r2` — guessing semantic names like `maxFeePpm`). Research
finding (see research.md R2): the on-demand lookup **already** returns the full field list —
but the model constructs the struct on attempt 1, before ever looking it up, so the fix is
to surface the fields **proactively** in the grounding, not to change the lookup response.

**Independent Test**: Build the grounding for a finding whose `callable_api` references a
struct/enum known to the index — confirm the draft prompt's grounding block includes that
type's member list (names + types), and that a nested struct type used as a field is also
expanded one level.

**Acceptance Scenarios**:

1. **Given** a `callable_api` signature that takes/returns a struct known to the index,
   **When** the grounding is built, **Then** the draft prompt includes that struct's full
   field list (names + types in declaration order).
2. **Given** such a struct whose fields include another struct/enum type, **When** the
   grounding is built, **Then** the nested type's members are also expanded (one level).
3. **Given** an enum referenced by the `callable_api`, **When** the grounding is built,
   **Then** the draft prompt includes its value list.
4. **Given** the on-demand lookup path (unchanged), **When** the model looks a struct up,
   **Then** the response still includes its fields (no regression to the existing behavior).

---

### User Story 3 - Lesson capture fires only on real progress (Priority: P2)

As the operator, I need the experiential-knowledge loop to propose a lesson **only when an
attempt genuinely resolved a stuck error** (it actually compiled / reached a better verdict)
— never when the model merely regressed into a *different* error — so the candidate queue
isn't polluted with false-positive lessons pairing a real error with a garbage "fix".

**Why this priority**: The human gate already quarantines a bad candidate (it stays pending,
never promoted), so this is not a security hole — but a capture heuristic that manufactures
junk wastes the reviewer's attention and undermines trust in the loop. Lower priority than
the two correctness fixes, but it directly protects the spec-014 loop's signal quality.

**Independent Test**: Drive the harness through a stuck→compiled transition (expect exactly
one captured candidate) and, separately, a stuck→regressed-to-a-different-error transition
(expect **zero** captured candidates).

**Acceptance Scenarios**:

1. **Given** an attempt stuck on an error-signature that the next attempt **compiles away**
   (reaches compiled/real_pass), **When** the loop evaluates capture, **Then** exactly one
   lesson candidate is emitted.
2. **Given** an attempt stuck on an error-signature that the next attempt replaces with a
   **different** error (a lateral change or regression, still not compiling), **When** the
   loop evaluates capture, **Then** **no** lesson candidate is emitted.
3. **Given** a genuinely resolved-then-recurring signature, **When** capture runs, **Then**
   dedup still holds (one candidate per distinct signature, per spec 014).

### Edge Cases

- A reply that is *only* a fenced block (no surrounding prose) → extracted unchanged (the
  current happy path must not regress).
- A reply with multiple fenced blocks → the Solidity source is taken as the span from the
  first real Solidity token to the last, so an explanatory second block doesn't corrupt it.
- A struct with zero members, or an enum, or a type the index doesn't know → the lookup
  response degrades gracefully (empty field list / existing "not found" behavior), never
  raises.
- Capture when the "better" verdict is `compiled` but not `passed` → still counts as real
  progress (a previously-uncompilable signature now compiles); a `vacuous_pass` (empty test)
  does **not** count as progress.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The harness MUST extract the Solidity source from a model reply by taking the
  span from the first real Solidity token (`// SPDX`, `pragma`, `import`, `contract`,
  `interface`, `library`, `abstract contract`) to the last, discarding any leading/trailing
  prose and fence markers — before writing the PoC file.
- **FR-002**: If a reply contains no Solidity token, the harness MUST treat it as a failed
  draft/fix and MUST NOT write an empty or prose-only PoC file.
- **FR-003**: In tool-calling protocol mode, if the round-trip yields no Solidity, the
  harness MUST fall back to the marker protocol for that finding rather than emit an empty
  file.
- **FR-004**: The grounding built for a finding MUST proactively include the full member
  list (field names + types in declaration order; enum values) of every struct/enum
  referenced by its `callable_api` signatures, shown in the draft prompt — so the model has
  the fields before it constructs the type, without needing a lookup.
- **FR-005**: When a referenced struct's fields include another struct/enum type, that
  nested type's members MUST also be expanded (one level of nesting). The existing on-demand
  lookup response (which already returns fields, research.md R2) MUST remain unchanged.
- **FR-006**: The experiential-knowledge-loop capture MUST fire only on a transition into a
  genuinely-better verdict (the attempt compiled / reached compiled or real_pass, clearing
  the previously-stuck signature) — never on a lateral change to a different error, a
  regression, or a vacuous pass.
- **FR-007**: Dedup-by-error-signature and the human-gated promotion of spec 014 MUST remain
  unchanged; only the capture *trigger condition* is tightened.
- **FR-008**: All behavior MUST be verifiable offline via the existing fake-model/fake-sandbox
  harness — no model, Docker, network, or paid API; no new runtime dependency.
- **FR-009**: No kernel trust invariant, the DATA-wrap rule, the SourceType hierarchy, or the
  promotion gate may change; this is harness-only hardening.

### Key Entities *(include if feature involves data)*

- **Model reply**: the raw text (or tool round-trip result) returned for a draft/fix; may be
  clean Solidity, prose-wrapped Solidity, prose-only, or empty.
- **Extracted PoC source**: the clean Solidity span written to the PoC file (or the "no
  code" signal that fails the draft/fix).
- **Lookup response**: the text injected back to the model for a resolved symbol; for a
  struct/enum it now carries the member list.
- **Capture transition**: the (previous verdict/signature → current verdict/signature) pair
  the loop inspects; a lesson is captured only when it represents real progress.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A prose-wrapped reply yields a PoC file containing **only** Solidity (0 prose
  lines, 0 fence markers); a prose-only reply yields **no** file written and a failed-draft
  signal.
- **SC-002**: A tool-mode round-trip that returns no Solidity results in a marker-protocol
  retry, not an empty PoC (0 empty-file/vacuous-pass outcomes from this cause).
- **SC-003**: The draft-prompt grounding for a finding contains **100%** of the fields
  (names + types) of every struct/enum referenced by its `callable_api`, nested types
  expanded one level; the on-demand lookup still returns fields (no regression).
- **SC-004**: A stuck→compiled transition produces **exactly one** lesson candidate; a
  stuck→different-error (lateral/regression) transition produces **zero**.
- **SC-005**: Spec-014 dedup and human-gated promotion behave identically to before (no
  regression in the loop's security/dedup tests).
- **SC-006**: The full offline suite passes with the new tests; no new runtime dependency;
  no change to any kernel-invariant test.

## Assumptions

- The "user" is the maintainer/operator; this is internal harness hardening, not an
  end-user feature.
- "Real Solidity token" is the set `// SPDX`, `pragma`, `import`, `contract`, `interface`,
  `library`, `abstract contract`; a reply's source is the span from the first such token to
  the last non-prose line. This covers the observed prose-prefix and empty-output cases.
- The symbol index already builds struct/enum member lists and the lookup already returns
  them (research.md R2); the fix surfaces those existing definitions **proactively** in the
  grounding for types the `callable_api` references — no new parsing, no lookup change.
- "Genuinely-better verdict" for capture means the attempt reached `compiled` or `real_pass`
  (the harness's existing verdicts), clearing the prior signature; `vacuous_pass` and any
  still-failing attempt do not qualify.
- Marker vs tool protocol selection already exists (`--lookup-protocol`); the fallback reuses
  it, it does not add a new protocol.
- This is driven by the observed live H-01 run; it does not attempt to make H-01 converge
  (its deeper scaffold/synthesis blocker is out of scope and deferred).
