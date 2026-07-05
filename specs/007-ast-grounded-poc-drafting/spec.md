# Feature Specification: AST-Grounded, Agentic Lookup for PoC Drafting

**Feature Branch**: `007-ast-grounded-poc-drafting`

**Created**: 2026-07-05

**Status**: Draft

**Input**: User description: "AST-grounded, agentic lookup for PoC drafting (SR-agent PoC-workability harness). Motivation: scripts/poc_queue_runner.py grounds the local model's PoC drafts with STATIC, regex-extracted context blocks... the model invents a plausible-but-nonexistent identifier/field because the real one wasn't visible in the static blocks we happened to think to extract — first invented interface names, then invented method signatures, then ignored access-control modifiers already present in context, then invented struct field names... because struct definitions are never expanded anywhere in the static context blocks. Every fix so far is architecturally the same shape: discover one new class of invented identifier, write one more regex-based extractor, add one more static block to the prompt. Scope: (1) Replace regex-based Solidity parsing with a real AST parser and build a queryable symbol index; (2) add an agentic lookup protocol to the draft/fix loop so the model can ask for any symbol's real definition on demand, bounded per attempt; (3) existing static grounding blocks stay as a fast-start baseline (hybrid, not replacement) and reimplementing them on the AST index is secondary; (4) validate end-to-end against the actual stalled finding (H-01) without requiring full convergence to a passing PoC as a condition of success."

## User Scenarios & Testing *(mandatory)*

The "user" is the SR-agent **operator/maintainer** running the PoC-workability
harness — this is an internal capability/reliability feature for existing tooling,
not an end-user-facing product feature.

### User Story 1 - The model stops inventing struct fields it can't see (Priority: P1)

As the operator, when the harness drafts a PoC that needs to construct or read a
struct value (e.g. a `TCancelGuard` argument, a `TBalanceState` return value), I need
the model to use the struct's REAL field names and types, not a plausible-sounding
invention, so the draft doesn't fail to compile on a class of mistake we've already
seen repeatedly this session.

**Why this priority**: This is the concrete, currently-live failure blocking progress
on the hardest known finding (H-01) — the immediate motivating case.

**Independent Test**: Feed the harness a finding whose target function takes/returns a
struct type not previously covered by the static grounding blocks (e.g., a newly
introduced struct never seen in file-map/callable_api before). The drafted PoC's
references to that struct's fields match the struct's real, parsed definition.

**Acceptance Scenarios**:

1. **Given** a finding whose target function signature references a struct type,
   **When** the model is unsure of that struct's fields, **Then** it can request and
   receive the struct's real field list before finalizing the PoC.
2. **Given** the model requests a symbol that genuinely does not exist in the target
   project, **When** the lookup resolves, **Then** the harness reports "not found" —
   it never fabricates a plausible-looking definition.

---

### User Story 2 - The fix generalizes to identifier classes we haven't hit yet (Priority: P1)

As the operator, I need the lookup mechanism to work for ANY named Solidity
construct (struct, enum, function, modifier, inherited state variable) — not just
structs — so that the NEXT class of invented identifier (which will happen; this
session already went imports → interfaces → signatures → modifiers → struct fields)
is closed by the same mechanism already in place, not by another one-off patch.

**Why this priority**: The whole point of this feature is to stop the "discover one
new failure shape, write one new extractor" pattern from this session. A lookup
mechanism that only covers structs would just be the fifth one-off patch, not a fix
to the pattern.

**Independent Test**: Request lookups for at least one symbol of each kind (struct,
enum, function, modifier) against the real target project and confirm each resolves to
its real, complete definition using the SAME mechanism (no per-kind special-casing
required to add a new kind later).

**Acceptance Scenarios**:

1. **Given** a symbol of any supported kind (struct/enum/function/modifier/state
   variable), **When** it is looked up by name, **Then** its real, complete definition
   is returned through the same resolution mechanism.
2. **Given** a new kind of invented-identifier failure is observed in the future,
   **When** a maintainer investigates, **Then** the fix is "this symbol kind wasn't
   covered by the index yet" (an index gap) rather than "write a new regex."

---

### User Story 3 - Parsing is grammar-correct, not pattern-matched (Priority: P2)

As the operator, I need the harness's understanding of the target project's Solidity
code to come from parsing its actual grammar, not from hand-written text patterns, so
that extraction bugs like this session's modifier-annotation deduplication collision
(two functions sharing a modifier producing byte-identical annotation text, silently
dropping one) stop recurring as a category.

**Why this priority**: Lower priority than shipping the lookup capability itself
(User Stories 1-2), but addresses the root cause of why regex-based extraction kept
needing bug fixes this session, and de-risks every future addition to the grounding
system.

**Independent Test**: Parse a real target file already known to have previously
tripped up regex-based extraction (structs with fields, functions with multiple
modifiers) and confirm the parsed result is complete and correct without needing
extraction-order-dependent workarounds.

**Acceptance Scenarios**:

1. **Given** a real Solidity source file from the target project, **When** it is
   parsed, **Then** every contract, struct (with all fields), function (with all
   modifiers), and enum (with all values) it declares is captured correctly.
2. **Given** two functions in the same file that happen to share an identical set of
   modifiers, **When** both are indexed, **Then** neither's information is lost or
   conflated with the other's.

---

### User Story 4 - Evidence from the hardest known case (Priority: P2)

As the operator, I need to see whether this mechanism actually changes what happens on
the finding that has stalled every attempt so far (H-01), so I know whether this lever
is worth keeping — without requiring it to fully solve H-01 as a condition of the
feature being considered done.

**Why this priority**: Validates the feature against real, already-known-hard evidence
rather than only synthetic tests; lower priority than shipping the mechanism itself
because a negative or inconclusive result is still a valid, useful outcome.

**Independent Test**: Run the harness against H-01 with the lookup mechanism enabled
and record what happened (whether the model used lookups, whether invented-identifier
errors decreased, whether it progressed further than prior runs) as a documented
result — a passing PoC is not required for this test to be considered complete.

**Acceptance Scenarios**:

1. **Given** the previously-stalled finding H-01, **When** a live run is executed with
   the lookup mechanism enabled, **Then** the run's outcome and whether/how the
   mechanism was used is recorded and reported, regardless of whether the PoC
   ultimately passes.

### Edge Cases

- What happens when the model asks for a symbol name that doesn't parse as a valid
  identifier, or asks for something absurdly broad (e.g. an entire contract's full
  source)? → The lookup must have a defined, bounded response (e.g. "not found" or a
  size-capped definition), never an unbounded dump that defeats the purpose of
  targeted lookup.
- What happens when the model keeps asking for lookups without ever finishing a draft
  (a runaway agentic loop)? → The number of lookups per attempt must be bounded
  (FR-004); once the bound is reached, the model must proceed with what it has.
- What happens when the target project's source fails to parse fully (a syntax the
  parser doesn't support, or a malformed file)? → The harness must degrade gracefully
  (fall back to the existing static grounding, per FR-005/FR-009) rather than crash
  the whole run.
- What happens when a symbol name is ambiguous (e.g. the same struct/function name
  exists in multiple contracts)? → The lookup must disambiguate in some defined way
  (e.g. return all matches with their containing contract, or prefer ones already in
  the finding's own grounding scope) rather than silently returning a wrong one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The harness MUST be able to resolve any named Solidity symbol (contract,
  interface, struct, enum, function, modifier) in the target project to its real,
  complete definition — for a struct, every field name and type; for a function, its
  full signature and every modifier; for an enum, every value.
- **FR-002**: Symbol resolution MUST be based on parsing the actual grammar of the
  source language, not on pattern-matching expected text shapes, so it does not
  silently miss or misparse validly-formatted code the original author didn't
  anticipate.
- **FR-003**: During PoC drafting and repair, the model MUST be able to request the
  definition of a symbol it is unsure about and receive the real definition before its
  answer is finalized.
- **FR-004**: The number of lookups the model may perform per PoC attempt MUST be
  bounded, so cost and latency stay predictable regardless of how often the model
  might ask.
- **FR-005**: The existing static grounding (file map, callable_api, scaffold,
  few-shot example) MUST continue to work as a fast-start baseline — this feature is
  additive; it does not require tearing out prior grounding levers first.
- **FR-006**: The lookup mechanism MUST be symbol-kind-agnostic — the same resolution
  path serves structs, enums, functions, modifiers, and state variables, so a
  newly-observed class of invented identifier is closed without a new one-off
  extractor.
- **FR-007**: The feature MUST be validated against a live run on the previously
  stalled finding (H-01), and the outcome (whether/how the mechanism changed model
  behavior) MUST be recorded — full convergence to a passing PoC is NOT a completion
  condition.
- **FR-008**: When the requested symbol does not exist in the parsed project, the
  lookup MUST report "not found" — it must never fabricate a plausible-looking
  definition (consistent with the positive-signal doctrine in
  [docs/eval-principles.md](../../docs/eval-principles.md)).
- **FR-009**: Symbol resolution MUST degrade gracefully (fall back to existing static
  grounding) if the target project's source fails to parse fully, rather than aborting
  the run.

### Key Entities

- **Symbol**: a named Solidity construct (contract/interface/struct/enum/function/
  modifier/state variable) with a kind, its real definition (fields+types for a
  struct, signature+modifiers for a function, values for an enum), and its source
  location.
- **Symbol Index**: the queryable structure built from parsing the target project,
  mapping names to Symbols; the single source of truth both the static grounding
  blocks and the agentic lookup draw from.
- **Lookup Request**: an in-flight request, made by the model during drafting/repair,
  naming a symbol whose real definition it needs.
- **Lookup Budget**: the bounded count of lookups permitted per PoC attempt.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Any struct, enum, function, or modifier referenced by a target
  codebase's real source can be resolved to its exact, complete definition without a
  maintainer writing new per-symbol-kind extraction code.
- **SC-002**: The specific extraction-bug category observed this session (two symbols
  sharing identical rendered text causing one's information to be silently dropped)
  cannot recur, because resolution no longer depends on rendered-text deduplication.
- **SC-003**: A live run against the previously-stalled finding (H-01) produces a
  recorded, honest account of whether the lookup mechanism was used and whether it
  changed the outcome — not silence or an untested claim.
- **SC-004**: The number of lookups used in any single PoC attempt is visible in the
  harness's own run log and never exceeds the configured bound.
- **SC-005**: A lookup for a symbol that doesn't exist in the real project is reported
  as not-found in 100% of such cases (never silently fabricated).

## Assumptions

- The "operator" is the person running `scripts/poc_queue_runner.py` — this is an
  internal capability feature for existing tooling, not an end-user product feature.
- This applies specifically to the Solidity/EVM target domain the PoC-workability
  harness already operates in; a future non-Solidity target is out of scope (YAGNI —
  generalize if and when a second language target actually appears).
- "Agentic lookup" here means the model can request a symbol's definition mid-turn
  within the existing draft/fix loop of the standalone PoC harness — it does NOT mean
  wiring this into the kernel's `OrchestratorLoop`/ReAct tool-dispatch machinery, which
  remains a separate, deliberately-unrelated system (per existing project convention:
  the PoC-workability harness is a standalone experiment/tool, not part of the secure
  kernel's tool-call path).
- The exact protocol by which the model signals a lookup request (e.g., a recognizable
  text marker vs. a structured tool-call schema) is a design decision, not a
  scope-level ambiguity, and is resolved during planning based on what's reliably
  supported across the local models already in use this session.
- Reimplementing the existing static grounding blocks (file map, callable_api,
  scaffold rendering) on top of the same Symbol Index is desirable for consistency but
  explicitly secondary — it must not block delivering the lookup capability itself.
- No prior PoC-success-rate baseline exists to compare against; this feature's
  validation (User Story 4 / SC-003) is about observing and honestly recording change,
  not hitting a numeric target.
