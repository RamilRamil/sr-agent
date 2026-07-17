# Research: Inherited-Base Repair Guards (spec 024)

Every decision below is grounded in **captured compiler output from the live report→PoC run**
(`poc_run.log`, 2026-07-16, outside the repo), not in recollection or solc documentation.
Two of them overturn assumptions the feature was originally specified on.

## Decision 1: Match the message TEXT, never the numeric error code

**Finding**: The feature was specified against solc error **2333**. The live output shows the real
code is **9097**:

```
Error (9097): Identifier already declared.
```

**Decision**: key recognition on the literal substring `Identifier already declared`. Record `9097`
in a comment only.

**Rationale**: this is exactly the convention the four existing hints already follow — every one of
them matches TEXT (`Member "X" not found`, `Source "X" not found`, `Identifier not found`,
`Wrong argument count`) and carries its code (9582/6275/7920/2904) only in a comment. Codes vary by
solc version and declaration context; the message string is what the harness has always trusted.
Had we matched `2333`, the guard would have silently never fired — the same class of failure as the
`gemini-2.5-flash` model-list rot: a curated constant that looks authoritative and is simply wrong.

**Alternatives considered**: matching both code and text (rejected — the code adds no discriminating
power over the text and reintroduces the rot risk); matching a code set `{2333, 9097}` (rejected —
guessing at codes we have never observed).

## Decision 2: The "invented API" diagnosis was wrong — finding-2 is a scope error

**Finding**: finding-2 was recorded as the model inventing a method `unstakeCooldown` on `StrataCDO`
(the case that justified escalating to a stronger hosted model). The live output refutes it. The
scaffold base declares the name for real:

```
test/…/…Deploy.t.sol:55:     UnstakeCooldown internal unstakeCooldown;
```

and the PoC's last attempt reads:

```solidity
UnstakeCooldown unstakeCooldown = UnstakeCooldown(address(cdo.unstakeCooldown()));
```

`unstakeCooldown` is a real, already-deployed state variable of the inherited base. The model reached
it through a wrong qualifier (`cdo.`), producing `Error (9582): Member "unstakeCooldown" not found …
in contract StrataCDO`.

**Decision**: treat this as a deterministic scope-repair case (US3), not a model-capability limit.

**Consequence**: the "weak model invents APIs → escalate to a stronger model" hypothesis was built on
a misreading. Both live failures (findings 2 and 5) are harness gaps. The blocked GLM/Gemini-pro
experiment was never needed to fix them.

## Decision 3: The existing 9582 hint actively misdirects on this shape — refine it, narrowly

**Finding**: today's entry answers `Member "X" not found in contract Y` with
`` `Y` has NO member `X`. Use only its real functions: <Y's signature list> ``. For finding-2 that is
true but harmful: it sends the model to hunt a substitute function on `StrataCDO`, when the fix is to
drop the `cdo.` qualifier entirely. The live burn-down shows the cost — attempts 2 and 3 both died on
the same 9582 after the model had already self-fixed the 9097:

| finding | att 1 | att 2 | att 3 | outcome |
|---|---|---|---|---|
| 2 | 9097 + 9582 | 9582 | 9582 | exhausted |
| 5 | 9097 | 9097 | 9097 | exhausted |

**Decision**: refine the 9582 entry ONLY when the scaffold text positively confirms `X` is a state
variable it declares. Then say: `X` is the inherited base's own state variable — already declared and
deployed — reference it directly, without the `Y.` qualifier. In every other case (no scaffold, no
matching declaration, ambiguity) return today's guidance **byte-identical**.

**Rationale**: the misdirection is only provable when we can show the name really is the base's. A
positive-evidence gate makes the refinement impossible to misfire, and keeps the blast radius on the
one existing hint to a strictly-narrower condition than it handles today.

**Alternatives considered**: replacing the 9582 hint wholesale (rejected — it is correct and useful
for genuine member errors); adding a separate unconditional "maybe it's on the base" nudge (rejected
— an unconditional maybe is noise, and noise is what we are removing).

## Decision 4: Extraction must not assume type-name casing, and types may differ

**Finding**: finding-5's collision:

```
Base: sNUSDAprPairProvider internal provider;
PoC:  AprPairProvider      public   provider;
```

Two traps here. The base's type **starts lowercase** (`sNUSDAprPairProvider`) — the existing
`_STATE_VAR_TYPE_RE` (`\b([A-Z]\w*)\s+(?:internal|public|private)\s+\w+\s*;`) would not match it. And
the two declarations have **different types**, so "use the inherited one" would not typecheck.

**Decision**: a sibling pattern that captures `<type> <visibility> <name>;` with `\w+` for the type
(no casing assumption) and captures the NAME, which is what both blocks share and what the guidance
must name. The guidance always offers both routes — use the inherited variable, **or** rename yours if
a genuinely distinct variable is intended — precisely because the types can differ.

**Rationale**: the existing type-regex is used for a different question ("does the scaffold declare an
instance of type T"), where uppercase-type was a safe-enough heuristic. Ours asks "what NAME collided",
and the live data proves casing carries no meaning. Reusing the existing regex would silently miss
finding-5 — the very case this feature exists for.

## Decision 5: Structure of the error block — what is parseable, and the honest fallback

**Finding**: both live blocks share one shape — a primary pointer at the base's declaration, a
`Note: The previous declaration is here:` pointer at the PoC's own file, and both underlined source
lines declaring the SAME name:

```
Error (9097): Identifier already declared.
  --> <base file>:58:5:
58 |     sNUSDAprPairProvider internal provider;
Note: The previous declaration is here:
  --> audit/poc/5.t.sol:24:5:
24 |     AprPairProvider public provider;
```

**Decision**: extract the declared name from the underlined source lines within the block. Not every
redeclaration is a visibility-qualified state variable (a local, a function, a contract name could
collide), so when no name is confidently parseable, emit the generic-but-correct instruction (do not
redeclare an inherited identifier; rename or drop the duplicate) rather than a specific claim.

**Rationale**: FR-004. A wrong specific name is worse than a right generic one — the model would chase
an identifier that isn't there. Under-firing into generic guidance is the correct conservative bias,
consistent with the matcher discipline throughout this project.

## Decision 6: The scaffold must be threaded into the hint layer

**Finding**: `_targeted_hints(forge_output, callable_api, file_map, code="", symbol_index=None)` does
not receive the scaffold, but the caller has `scaffold` in scope (it already reads it at the same call
site for the defect gate: `_poc_defects(code, target_stems, scaffold_used=bool(scaffold))`).
`SymbolIndex` exposes `provides_state_var_type(contract, type_name)` — which answers about a **type**,
not a **name**, so it cannot answer FR-008's question.

**Decision**: pass the scaffold text as a new optional parameter, defaulting to absent. Absent → the
FR-008 refinement cannot fire and today's behavior stands (FR-009), which also keeps every existing
caller and test valid without change.

**Rationale**: an optional parameter with a behavior-preserving default is the smallest change that
makes the evidence available. Extending `SymbolIndex` with a state-variable-NAME query was considered
and rejected for this feature: the scaffold text is already the authority the PoC is told to inherit,
a regex over it is sufficient and offline, and widening the shared index is a larger blast radius than
this hardening warrants.

## Decision 7: Name the declaring location from the COMPILER, never by re-parsing the scaffold

**Finding**: the plan first proposed enriching the redeclaration hint with the base's name via the
existing `_scaffold_base_name`. Reading the code refutes that: `_scaffold_base_name` is written for a
SINGLE scaffold file's text, and `read_scaffold` correctly calls it **per file**. But what reaches
`_targeted_hints` is `read_scaffold`'s OUTPUT — a rendered, multi-file blob of `// [test_scaffold] …`
headers plus sources. Applied to that blob it would compute "leaves" across all files and return
`leaves[-1]` — the last file's leaf, potentially naming the **wrong** base.

Meanwhile the compiler already reports what we want, per collision:

```
  --> <base file>:58:5:            ← the prior declaration
  --> audit/poc/5.t.sol:24:5:      ← the PoC's own
```

**Decision**: take the declaring location from the error block itself. The two file paths are
distinguished by the harness's known PoC location (`POC_SUBDIR`): the one NOT under it is the base's.

**Rationale**: authoritative (it is the compiler's own report), per-collision (attributable, which a
scaffold-wide parse is not), and it needs no scaffold at all — removing a dependency rather than adding
one. Naming the wrong base would be exactly the misleading specific claim FR-004 exists to prevent.

**Alternatives considered**: parsing our own rendered header (`` INHERIT the contract `(\w+)` ``) —
rejected, it yields a base per BLOCK with no way to attribute a given collision to one; extending
`_scaffold_base_name` to handle blobs — rejected, it would complicate a function whose single-file
contract is correct and relied on elsewhere.

## Decision 8: Strip comments before the FR-008 evidence gate

**Finding**: the two existing scaffold-parsing paths disagree. `_scaffold_base_name` calls
`_strip_comments` before parsing; `scaffold_missing_types` applies `_STATE_VAR_TYPE_RE` to raw scaffold
text. A commented-out declaration would therefore read as a real one.

**Decision**: follow `_scaffold_base_name` — run the existing `_strip_comments` over the scaffold before
applying `_BASE_STATE_VAR_RE`.

**Rationale**: FR-008's gate is the one thing standing between "refine" and "misdirect", and its whole
justification is that it fires only on positive evidence. Commented-out source is not evidence. The
helper already exists, costs nothing, and is offline. (`scaffold_missing_types`'s looser parse is out of
scope here — it answers a different question and changing it is not this feature's business.)

## Test-fixture rule (non-negotiable)

The live log grounds the DESIGN; it must not enter the repo. Every fixture is invented — synthetic
contract, variable and file names that resemble nothing in any audited target — reproducing only the
SHAPE of the compiler output (memory `feedback_no_target_code_in_agent`). The traps the live data
revealed are pinned by synthetic analogues: a lowercase-initial type, a differing-types collision, and
a member-not-found whose name the synthetic scaffold declares.
