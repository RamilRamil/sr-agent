# Feature Specification: Nested-Type Import Determinism

**Feature Branch**: `016-nested-type-import-determinism`

**Created**: 2026-07-14

**Status**: Draft

**Input**: User description: "Make the harness deterministically fix the nested-type
named-import blocker that stalled H-01 six times, instead of relying on a retrieved
'suggestion' the model doesn't obey. The knowledge loop surfaced the right lesson (verified)
and the 30B model still named-imported nested struct/enum types (`Error 2904`). The mistake
is deterministically detectable — the symbol index knows a type's containing contract — so
fix it deterministically in three index-driven layers: a mechanical import guard, a
grounding note, and an authoritative repair hint. Offline-testable; no kernel-invariant
change."

## User Scenarios & Testing *(mandatory)*

The "user" is the SR-agent **maintainer/operator** running the PoC-workability harness. This
feature turns one repeatable, mechanically-detectable model mistake — named-importing a
struct/enum that is declared *inside* a contract/interface — into a deterministic fix,
because a retrieved lesson (a *suggestion*) proved insufficient to change the model's
behavior even when it was the top result injected into the prompt. The determinism is
index-driven: only names the symbol index actually knows as nested are ever touched.

### User Story 1 - The PoC's nested-type imports are mechanically corrected (Priority: P1) 🎯 MVP

As the operator, I need the harness to automatically rewrite an invalid named-import of a
nested type into the valid form — import the containing contract/interface, remove the
named-import, AND rewrite the type's bare uses in the body to `Container.Type` — on the
drafted PoC and on every fix attempt, so a known-mechanical error never survives to the
compiler regardless of what the model writes. (The bare-use rewrite is required, not
optional: verified against the real PoC, the model named-imports these types and uses them
bare, so fixing only the import would produce an `undefined identifier` error instead.)

**Why this priority**: This is the model-independent fix and the direct unblocker — H-01 is
one import line from compiling. It works even if the model repeats the mistake forever.

**Independent Test**: Feed a PoC that named-imports a type the index knows as nested → the
guard rewrites it (removes the nested name from the named-import, ensures the container is
imported); feed a PoC that named-imports a genuinely top-level type → it is left unchanged.

**Acceptance Scenarios**:

1. **Given** a PoC with `import { NestedType } from "…";` where the index knows `NestedType`
   is declared inside `Container`, and the body uses `NestedType` **bare**, **When** the guard
   runs, **Then** `NestedType` is removed from that named-import, `Container` is imported
   (added if absent), and every bare use of `NestedType` in the body is rewritten to
   `Container.NestedType` (already-qualified uses left untouched) — so the code compiles.
2. **Given** a PoC that named-imports a mix of nested and top-level names from one line,
   **When** the guard runs, **Then** only the nested names are removed; the top-level names
   remain named-imported.
3. **Given** a PoC that named-imports only genuinely top-level types (or types the index
   doesn't know), **When** the guard runs, **Then** the code is unchanged (no false rewrite)
   and it reports "no change".
4. **Given** the guard rewrote imports, **When** it runs, **Then** it logs a
   `postfix_nested_import` event (like the existing mechanical guards).

---

### User Story 2 - The model is told how to reference a nested type up front (Priority: P1)

As the operator, I need the proactive struct/enum grounding (spec 015) to show, for any
nested type, **how to reference it** — not just its fields — so the model constructs and
imports it correctly the first time instead of named-importing it.

**Why this priority**: Prevention at the point the model first sees the type; pairs the
field list with the reference/import guidance the on-demand lookup already provides.

**Independent Test**: Build the grounding for a `callable_api` referencing a nested struct →
the grounding includes both the field list and the note "`X` is nested inside `Container` —
import `Container`, reference as `Container.X`, do not `import { X }`"; a top-level type gets
the fields but no such note.

**Acceptance Scenarios**:

1. **Given** a `callable_api` referencing a struct declared inside a contract/interface,
   **When** the grounding is built, **Then** it includes that type's fields AND the
   nested-reference note (import the container; use `Container.Type`; do not named-import).
2. **Given** a referenced type that is genuinely top-level, **When** the grounding is built,
   **Then** its fields are shown with no nested-reference note.

---

### User Story 3 - A nested named-import error gets an authoritative repair hint (Priority: P2)

As the operator, I need the compiler-error-to-hint step to recognize the "Declaration not
found … referenced as" error for a nested type and emit the exact fix, so the repair is an
authoritative instruction, not a soft suggestion — closing the loop when the model reaches
the type via a lookup rather than the proactive grounding.

**Why this priority**: Reinforces US1/US2 on the feedback path; lower priority because US1
already corrects the artifact mechanically, but an authoritative hint helps the model learn
the correct form within the run.

**Independent Test**: Run the hint step on a synthetic "Declaration \"X\" not found …
referenced as …" error where the index knows `X` as nested → the hint names `Container`,
says to remove the named import and use `Container.X`; the same error for a genuinely
unknown/invented name → no nested-type hint.

**Acceptance Scenarios**:

1. **Given** a compiler error `Declaration "X" not found … referenced as …` and the index
   knows `X` as a nested struct/enum in `Container`, **When** hints are generated, **Then**
   an authoritative hint says to remove `import { X }` and reference it as `Container.X`
   (importing `Container` if needed).
2. **Given** the same error shape for a name the index does not know as nested, **When**
   hints are generated, **Then** no nested-type hint is emitted (no misleading advice).

### Edge Cases

- A nested type imported via an aliased or multi-line named import → handled or safely left
  unchanged (never a corrupting partial rewrite).
- The container is already imported → the guard only removes the nested name; it does not
  duplicate the container import.
- A name the index knows as BOTH a top-level and a nested declaration (ambiguous) → treated
  conservatively (not rewritten) to avoid a false correction.
- The guard must be idempotent: running it twice yields the same result and reports "no
  change" the second time.
- Determinism boundary: the guard/hint act ONLY on names the index actually knows as nested;
  an invented/unknown name is left to the existing "not a real symbol" handling.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The harness MUST provide a mechanical guard that, given a PoC's source and the
  symbol index, (a) removes any named-imported name the index knows as a struct/enum with a
  non-empty containing contract, (b) ensures that containing contract is imported (added if
  absent), and (c) rewrites each such type's **bare** uses in the body to `Container.Type`
  (leaving already-qualified uses untouched). It MUST return whether it changed the code.
- **FR-002**: The guard MUST be applied to the drafted PoC and to every fix attempt (the same
  points the existing mechanical guards run).
- **FR-003**: The guard MUST NOT alter a named-import of a genuinely top-level type or of a
  name the index does not know (no false rewrites), and MUST be idempotent.
- **FR-004**: When the guard changes the code, it MUST log a `postfix_nested_import` event
  consistent with the other mechanical guards.
- **FR-005**: The proactive struct/enum grounding MUST, for any expanded type with a
  non-empty containing contract, include a nested-reference note (import the container;
  reference as `Container.Type`; do not named-import), in addition to the fields.
- **FR-006**: The compiler-error-to-hint step MUST recognize a "Declaration not found …
  referenced as" error whose subject the index knows as a nested struct/enum and emit an
  authoritative fix naming the container and the `Container.Type` form; it MUST NOT emit a
  nested-type hint for a name the index does not know as nested.
- **FR-007**: All behavior MUST be verifiable offline via the existing fake-model/fake-sandbox
  harness and symbol-index fixtures — no model, Docker, network, or paid API; no new
  runtime dependency.
- **FR-008**: No kernel trust invariant, the DATA-wrap rule, the SourceType hierarchy, the
  promotion gate, or the knowledge-loop retrieval behavior may change; this feature ADDS
  deterministic repair alongside retrieval.

### Key Entities *(include if feature involves data)*

- **Nested type**: a struct/enum whose declaration is inside a contract/interface — the
  symbol index records its containing contract (empty for a top-level type). This flag is the
  determinism source.
- **Named-import statement**: a `import { A, B, … } from "path";` line in the PoC; the guard
  partitions its names into nested (to remove) and non-nested (to keep).
- **Container import**: the `import { Container } from "path";` the guard ensures is present
  so `Container.Type` references resolve.
- **Nested-import hint / note**: the authoritative repair text (hint path) and the proactive
  guidance (grounding path) telling the model the correct reference form.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A PoC that named-imports a known nested type is rewritten so it compiles that
  reference; a PoC named-importing only top-level/unknown types is byte-unchanged (0 false
  rewrites).
- **SC-002**: The guard is idempotent — a second run reports "no change" and produces
  identical output.
- **SC-003**: The proactive grounding for a nested referenced type contains the
  nested-reference note 100% of the time; a top-level type never gets it.
- **SC-004**: A synthetic `Declaration not found … referenced as` error for an index-known
  nested type yields the authoritative `Container.Type` hint; an unknown name yields none.
- **SC-005**: The full offline suite passes with the new tests; no new dependency; no
  kernel-invariant test changes; the knowledge-loop tests are unaffected.
- **SC-006**: On a live re-run, the specific `Error 2904` nested-import stall no longer
  recurs (H-01 advances past it) — validated opportunistically, not required for merge.

## Assumptions

- The symbol index already records a type's containing contract (`Symbol.contract`, empty for
  top-level); this feature reads that flag — no new parsing.
- The container's import path is obtainable from the index / file map the harness already
  builds (same source the existing import-path hints use).
- "Nested type" covers struct and enum declarations inside a contract/interface — the case
  observed live (`TExitUpperBounds`, `TExitParams` inside `ISharesCooldown`).
- This feature ADDS determinism alongside the knowledge loop; it does not change retrieval or
  the "suggestion, not control" stance (the loop still surfaces the lesson — this just makes
  the mechanical case not depend on the model obeying it).
- It does not attempt to make H-01 fully converge: after this it should get past the
  nested-import error, but the deeper scaffold/synthesis blocker (SharesCooldown not deployed;
  spec-011 `_synth/…` import path) is separate and deferred.
- Roadmap meta-note: this is the concrete evidence that, for a mechanical, index-detectable
  mistake, deterministic repair beats a retrieved suggestion.
