# Feature Specification: Deterministic Repair Guard for "Identifier Already Declared"

**Feature Branch**: `024-identifier-collision-guard`

**Created**: 2026-07-16

**Status**: Draft

**Input**: User description: "Deterministic compile-repair guards for the two mechanical non-compile failures observed in the live report→PoC run, both rooted in one confusion: the drafted PoC does not understand what its inherited test-scaffold base already gives it. (a) It re-declares an identifier the base already declares (solc 'Identifier already declared') — no hint exists, so the model hits the same wall every attempt. (b) It reaches a real base state variable through a wrong qualifier (solc 'Member X not found ... in contract Y') — a hint exists but MISLEADS, sending the model to hunt the wrong contract's function list."

**Live-run evidence (2026-07-16, `poc_run.log`)** — this spec is grounded in captured compiler output, not recollection:

| finding | att 1 | att 2 | att 3 | outcome |
|---|---|---|---|---|
| 2 | 9097 + 9582 | 9582 | 9582 | exhausted |
| 5 | 9097 | 9097 | 9097 | exhausted |

Two corrections this evidence forced on the original framing: the error code is **9097**, not 2333 (so the guard matches the message TEXT, as every existing hint does — codes live only in comments); and finding-2's `unstakeCooldown` was **never an invented API** — it is a real state variable the scaffold base declares (`UnstakeCooldown internal unstakeCooldown;`), which the PoC reached as `cdo.unstakeCooldown()`. Both failures are deterministic harness gaps, not model-capability limits.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A redeclaration collision is repaired in one shot, not quarantined (Priority: P1)

The harness drafts a PoC that inherits the project's test-scaffold base and then declares a variable whose name the base already declares. The compiler rejects it with a specific, well-known error. Today the harness has no authoritative fix for this error, so it feeds the model a generic failure, burns its remaining draft attempts, and quarantines a PoC that was one rename away from compiling. With this feature, the harness recognizes the collision and hands the model an exact instruction — name the colliding identifier, state that the inherited base already declares it, and tell it not to redeclare (use the inherited one, or rename a genuinely distinct local) — so the next attempt compiles.

**Why this priority**: This is the entire feature. The live report→PoC run showed this exact mechanical failure waste attempts and produce a false "non-compile" outcome for a finding whose PoC was otherwise sound. It is the tier-1 "mechanical → deterministic guard" case in the project's non-compiling strategy, and it is the only user-visible behavior this feature adds.

**Independent Test**: Feed the deterministic hint layer a synthetic compiler output containing a real "Identifier already declared" error naming a concrete identifier; the layer returns a hint that names that identifier and instructs against redeclaration. Feed it output without that error; the hint does not appear.

**Acceptance Scenarios**:

1. **Given** compiler output reporting "Identifier already declared" for a named identifier, **When** the deterministic hint layer processes it, **Then** the returned guidance names that identifier and instructs the model not to redeclare an inherited identifier (use the inherited one or rename).
2. **Given** the same collision AND the compiler's output names the file holding the prior declaration, **When** the hint is produced, **Then** the guidance also names that declaring location for added authority, correctly distinguishing it from the PoC's own file.
3. **Given** compiler output whose "Identifier already declared" text does not expose a confidently parseable identifier name, **When** the hint is produced, **Then** a generic-but-correct instruction is returned (do not redeclare an inherited identifier; rename or drop the duplicate) rather than a specific claim naming the wrong identifier.

---

### User Story 2 - The guard never fires on unrelated errors (Priority: P1)

A maintainer must trust that this addition does not pollute other repairs. The new guidance appears only for a genuine redeclaration collision; every other compiler error the harness already handles (undeclared identifier, member-not-found, source-not-found, nested-type, wrong-argument-count) is unaffected, and clean or unrelated output produces none of the new guidance.

**Why this priority**: A hint that fires on the wrong error is worse than no hint — it would send the model chasing a non-existent collision and could break repairs that work today. Conservative, signature-exact firing is the project's standing anti-inflation discipline applied to compiler-error matching.

**Independent Test**: Feed the hint layer output for a different, already-handled error (e.g. an undeclared-identifier error) and clean output; the redeclaration guidance is absent in both, and the pre-existing hints for those errors are unchanged.

**Acceptance Scenarios**:

1. **Given** compiler output for an undeclared-identifier error (not a redeclaration), **When** the hint layer runs, **Then** the new redeclaration guidance is NOT present and the existing undeclared-identifier guidance still is.
2. **Given** compiler output with no relevant error, **When** the hint layer runs, **Then** no redeclaration guidance is produced.
3. **Given** output that would trigger the new guidance more than once, **When** the hint layer runs, **Then** the guidance appears once (consistent with the layer's existing de-duplication of repeated hints).

---

### User Story 3 - A real base state variable reached through a wrong qualifier is corrected, not misdirected (Priority: P1)

The PoC references a name that genuinely exists — it is a state variable the inherited base already declares and deploys — but reaches it through a wrong qualifier, as if it were a member of some other contract. The compiler reports the name is not a member of that contract. Today the harness answers with "that contract has no such member; use only its real functions" plus that contract's function list — which is true but **misdirecting**: it sends the model hunting for a substitute function on the wrong contract, when the correct fix is to drop the qualifier and use the inherited variable directly. With this feature, when (and only when) the missing member's name is confirmed to be a state variable the scaffold base declares, the guidance says so and instructs the model to reference it directly, unqualified.

**Why this priority**: In the live run this single misdirection consumed finding-2's last two attempts and drove it to `exhausted` — a PoC one qualifier away from compiling. It is the same root confusion as US1 ("the base already declares this"), surfacing as a different compiler error, and it is the difference between the harness helping and the harness actively steering wrong.

**Independent Test**: Feed the hint layer a synthetic "member not found" error for a name that the supplied synthetic scaffold declares as a state variable; the guidance identifies it as the base's own state variable and instructs unqualified direct use. Feed the same error for a name the scaffold does NOT declare; today's existing guidance is returned unchanged.

**Acceptance Scenarios**:

1. **Given** a "member not found on contract Y" error for a name the scaffold base declares as a state variable, **When** the hint layer runs, **Then** the guidance states the name is the inherited base's own state variable (already available, already deployed) and instructs the model to use it directly without the `Y.` qualifier.
2. **Given** the same error for a name the scaffold does NOT declare as a state variable, **When** the hint layer runs, **Then** the pre-existing "no such member — use its real functions" guidance is returned, byte-identical to today's behavior.
3. **Given** the same error but no scaffold is available to the harness, **When** the hint layer runs, **Then** the pre-existing guidance is returned unchanged (the refinement never fires without positive evidence).

---

### Edge Cases

- The colliding identifier name cannot be confidently parsed from the compiler output → emit correct generic guidance, never a misleading specific claim (US1 scenario 3).
- A base state-variable declaration whose TYPE begins with a lowercase letter (observed live: `sNUSDAprPairProvider internal provider;`) → must still be recognized; type-name casing carries no meaning.
- The colliding declarations have DIFFERENT types (observed live: base `sNUSDAprPairProvider internal provider` vs PoC `AprPairProvider public provider`) → "use the inherited one" may not typecheck, so the guidance must always also offer "rename yours if you genuinely need a distinct variable" (FR-002).
- The scaffold contains a COMMENTED-OUT declaration of the name → that is not evidence; the refinement must not treat commented-out source as a declaration (FR-008's gate must strip comments before matching).
- The named contract does have a member of that name but it is not visible (the compiler reports "not found **or not visible**") → the refinement still applies: the compiler has already ruled the qualified access out, and the base's own declaration is the accessible one. No suppression on this basis.
- The inherited base name is not available to the harness → still emit the identifier-named guidance without the base name (US1 scenario 2 degrades gracefully).
- Multiple distinct collisions in one compiler run → each real collision is addressed; identical guidance is de-duplicated (US2 scenario 3).
- Output contains both a redeclaration error and other handled errors → the redeclaration guidance is added alongside the others, none removed or altered.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The harness's deterministic compiler-error-to-fix layer MUST recognize the solc "Identifier already declared" declaration error (error code 2333) and produce an authoritative repair instruction for it.
- **FR-002**: The repair instruction MUST, when the colliding identifier name is confidently parseable from the compiler output, name that identifier and instruct the model NOT to redeclare it — the inherited scaffold base already declares it, so the model must use the inherited one, or rename to a non-colliding name if a genuinely distinct local is intended.
- **FR-003**: The instruction MUST identify WHERE the prior declaration lives, taken from the compiler's OWN output (which names the file and line of both colliding declarations) and distinguished from the PoC's own file by the harness's known PoC location; when the compiler output does not yield it, the instruction MUST still be produced without it. The declaring location MUST NOT be derived by re-parsing the scaffold, which cannot be attributed to a specific collision.
- **FR-004**: When the identifier name cannot be confidently parsed, the layer MUST emit correct generic guidance (do not redeclare an inherited identifier; rename or drop the duplicate) instead of a specific claim that could name the wrong identifier.
- **FR-005**: The guidance MUST fire ONLY on a genuine "Identifier already declared" signature and MUST NOT fire on any other compiler error or on clean output (conservative, anti-inflation matching).
- **FR-006**: Recognition MUST key on the compiler's message TEXT, not on a numeric error code, since the observed code (9097) differs from the one originally assumed; any numeric code MAY appear in an explanatory comment only.
- **FR-007**: Identifier extraction MUST NOT assume type-name casing — a declaration whose type begins with a lowercase letter MUST be recognized exactly as one beginning uppercase.
- **FR-008**: When the missing member named by a "member not found on contract Y" error is CONFIRMED to be a state variable declared by the scaffold base, the guidance MUST identify it as the inherited base's own state variable and instruct direct, unqualified use. Confirmation MUST ignore commented-out source, so that a commented-out declaration is never mistaken for evidence.
- **FR-009**: The refinement in FR-008 MUST fire ONLY on positive confirmation from the scaffold; absent a scaffold or absent a matching declaration, the pre-existing "member not found" guidance MUST be returned byte-identical to today's behavior.
- **FR-010**: Apart from the FR-008 refinement, the addition MUST NOT change, remove, or reorder any existing deterministic hint, nor alter the draft/compile/repair loop control flow, the mutation-verification step, or what counts as a compiled/passing PoC.
- **FR-011**: All guidance MUST be produced purely from the compiler output text and information the harness already holds, with no model call, no Docker, and no network — matching the existing deterministic hints.
- **FR-012**: Repeated identical guidance within one compiler run MUST be de-duplicated consistently with the layer's existing behavior.
- **FR-013**: The behavior MUST be validated by offline, deterministic tests over SYNTHETIC compiler output and synthetic scaffolds (invented, never real audited-target material): a redeclaration positive naming a concrete identifier, a lowercase-type variant, a differing-types variant, a declaring-location variant, an unparseable-declaration fallback, the FR-008 refinement positive, a commented-out-declaration negative, and negatives (an undeclared-identifier error, a member-not-found for a name the scaffold does not declare, no-scaffold, and clean output) where the new guidance does not fire.
- **FR-014**: Tests MUST follow the repository's established per-error-code layout for this hint layer, so each entry's tests and its regression guards live with the entry they cover.

### Key Entities

- **Compiler error output**: the text emitted by the compile step, the sole input the guidance is derived from.
- **Redeclaration collision**: the specific "Identifier already declared" condition where a drafted PoC redeclares an identifier its inherited base already declares.
- **Repair instruction / hint**: the authoritative, deterministic guidance string handed back to the model for the next draft attempt.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For compiler output containing a redeclaration collision that names an identifier, the harness produces guidance that names that identifier and instructs against redeclaration, 100% of the time and identically across runs.
- **SC-002**: For compiler output containing any other already-handled error, or clean output, the new guidance is produced 0% of the time, and all pre-existing guidance for those errors is unchanged.
- **SC-003**: A redeclaration collision that previously exhausted draft attempts and quarantined now receives, on its first repair, an instruction sufficient to remove the collision (rename/no-redeclare), demonstrated on synthetic output.
- **SC-004**: The guidance is produced with no model, Docker, or network involvement, and the full offline test suite passes including the new deterministic tests (which would fail if the guard stopped firing on a real collision or started firing on an unrelated error).
- **SC-005**: For a "member not found" error naming a name the scaffold declares as a state variable, the guidance instructs unqualified direct use 100% of the time; for a name the scaffold does not declare, or with no scaffold, the pre-existing guidance is returned byte-identical 100% of the time.
- **SC-006**: Replaying the two live-run failure shapes (a repeated redeclaration collision, and a member-not-found on a real base state variable) against the hint layer as synthetic fixtures yields, in both cases, guidance that names the correct mechanical fix — where today one yields nothing and the other yields misdirection.

## Assumptions

- The compile step surfaces the solc declaration error text (including the "Identifier already declared" phrasing and error code) in the output the hint layer already receives — the same channel from which the existing undeclared-identifier / member-not-found / source-not-found hints are derived.
- The identifier name, when parseable, is recoverable from the compiler output the harness already captures (the flagged declaration line under the source pointer); when it is not cleanly recoverable, generic guidance is the correct, honest fallback.
- The inherited scaffold base name and text, when available, come from the harness's existing scaffold handling; this feature does not introduce a new way to discover or resolve a scaffold.
- Exact-signature matching on the declaration error is the correct conservative bias: under-firing (falling back to generic or pre-existing guidance) is acceptable; misfiring on an unrelated error is not.
- The scaffold text is sufficient evidence for FR-008: a name declared as a state variable in the scaffold the PoC is told to inherit is, for the purpose of this guidance, the base's own state variable. Findings requiring deeper resolution through the base's own parents fall back to pre-existing guidance rather than guessing.
- The live-run log used to ground this spec lives outside the agent repository; only invented, synthetic fixtures derived from its SHAPE (never its names, paths, or contract identifiers) enter the repo.

## Out of Scope

- Any change to the deterministic hint entries other than the single, conservatively-gated "member not found" refinement of FR-008; the nested-type, source-not-found, wrong-argument-count and undeclared-identifier entries are untouched.
- Any change to the draft/compile/mutation loop control flow.
- Pre-compile static prevention of collisions (rewriting the drafted PoC source before compiling) — the harness's contract is to compile and repair from real compiler errors, not to mutate PoC source blind.
- Genuinely invented APIs (a PoC calling a method that exists nowhere in the project). The live run produced no such case — the one previously believed to be invented was a real base state variable reached through a wrong qualifier (US3) — so this remains hypothetical and is not addressed here.
- Any change to what counts as a compiled or passing PoC (the compile check, the vacuous-pass/defect gate, and the mutation-verification step are untouched).
- Any new model, Docker, or network dependency in the new code or its tests.
