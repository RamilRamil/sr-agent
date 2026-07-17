# Implementation Plan: Inherited-Base Repair Guards

**Branch**: `024-identifier-collision-guard` | **Date**: 2026-07-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/024-identifier-collision-guard/spec.md`

## Summary

Close the two deterministic harness gaps that drove findings 2 and 5 to `exhausted` in the live
report→PoC run, both rooted in one confusion — *the PoC does not know what its inherited scaffold base
already gives it*:

1. **New hint** on `Identifier already declared` (observed code 9097): name the colliding identifier
   and instruct the model not to redeclare what the base already declares — use the inherited one, or
   rename if a genuinely distinct variable is intended. Today there is no hint at all, so the model hit
   the same wall on 3/3 attempts.
2. **Narrow refinement** of the existing `Member "X" not found in contract Y` hint: when the scaffold
   positively confirms `X` is a state variable it declares, say so and instruct unqualified direct use.
   Today's answer ("use `Y`'s real functions") is true but misdirects, and burned finding-2's last two
   attempts.

Both are pure string/regex work over compiler output the harness already captures — no model, no
Docker, no network. Everything is grounded in [research.md](research.md), which overturned two
assumptions the spec was first written on (the error code, and the "invented API" diagnosis).

## Technical Context

**Language/Version**: Python 3.12 (existing harness code)

**Primary Dependencies**: none new — stdlib `re` only

**Storage**: N/A

**Testing**: pytest, offline, synthetic fixtures built in-test (no dataset, no Docker, no network)

**Target Platform**: operator CLI (`scripts/poc_queue_runner.py`), macOS/Linux

**Project Type**: single project — operator tooling on top of the kernel/pack

**Performance Goals**: N/A (regex over a bounded compiler-output tail, once per draft attempt)

**Constraints**: fully offline; deterministic (identical input → identical guidance); existing hints
byte-identical outside the one gated refinement

**Scale/Scope**: one new hint entry, one gated refinement of an existing entry, one new optional
parameter, one new module-level regex, plus unit tests. No new files in `sr_agent/`.

## Constitution Check

| Principle | Status | Rationale |
|---|---|---|
| **I. Secure-Kernel Trust Invariants** | ✅ PASS | Adds no new trust promotion. Compiler output is tool output; the guidance derived from it flows into the model prompt exactly as the four existing hints do. Nothing is promoted to `human_input`; no new source type is introduced. |
| **II. Human Authority** | ✅ PASS | No privileged or irreversible action; no `write_execute`-class surface touched. Crucially, this does NOT relax "findings are confirmed only by a passing PoC": `_compiled`, `_poc_defects`, `real_pass` and `mutation_verify` are untouched (FR-010). The guard helps a PoC *compile*; it cannot make one *pass*. |
| **III. Kernel / Pack Separation** | ✅ PASS | Change is confined to `scripts/` operator tooling, which already imports the pack. No kernel code, no pack code, no new kernel→pack import. |
| **IV. Human-Gated Knowledge Promotion** | ✅ PASS | No knowledge-store writes. The existing `_maybe_capture_lesson` path is untouched. |
| **V. No Paid-API Dependency** | ✅ PASS | Strengthens it: this work removes two failures previously (mis)attributed to needing a stronger *paid* model. The new code is pure stdlib regex and its tests need no model at all. |

**Gate result**: PASS, no violations, no justifications required. Complexity Tracking is empty by
consequence.

## Project Structure

### Documentation (this feature)

```
specs/024-identifier-collision-guard/
├── spec.md              # what & why (rewritten after the live-log evidence)
├── plan.md              # this file
├── research.md          # 6 decisions, each grounded in captured compiler output
├── quickstart.md        # how to read/extend the deterministic hint layer
├── tasks.md             # (/speckit-tasks)
└── checklists/
    └── requirements.md
```

No `data-model.md` (no entities/persistence) and no `contracts/` (no external interface — this is an
internal repair-guidance behavior, exercised through the existing CLI). Both are correctly omitted
rather than stubbed.

### Source Code (repository root)

```
scripts/
└── poc_queue_runner.py        # MODIFIED — the only production file
    ├── _BASE_STATE_VAR_RE     # NEW: <type> <visibility> <name>;  — \w+ type, captures NAME
    ├── _targeted_hints(...)   # MODIFIED: + optional `scaffold` param
    │   ├── (new)  Identifier-already-declared entry        → US1/US2
    │   └── (mod)  Member-not-found entry, gated refinement → US3
    └── _process_finding(...)  # MODIFIED: one line — thread `scaffold` through

tests/unit/
├── test_targeted_hints_9097.py  # NEW — US1/US2, offline, synthetic fixtures only
└── test_targeted_hints_9582.py  # NEW — US3 + the byte-identical regression guards
```

**Test layout** follows the repository's established convention: `tests/unit/test_targeted_hints_2904.py`
already names a hint's test file after the error code it covers. One file per code keeps each entry's
regression guards beside the entry they protect (FR-014). Those files import `_targeted_hints` directly
and need no environment guard — the sibling proves the import is side-effect-free.

**Structure Decision**: single project, existing layout. The harness (`scripts/poc_queue_runner.py`)
is the established home for operator tooling that imports the pack — the same rationale recorded in
spec 023's Decision 5. `SymbolIndex` (`scripts/solidity_index.py`) is deliberately **not** extended:
per research Decision 6 the scaffold text is the authority the PoC is told to inherit, and a regex
over it is sufficient, offline, and a far smaller blast radius than widening the shared index.

## Design

### The one new regex

`_BASE_STATE_VAR_RE` captures `<type> <visibility> <name>;` with `\w+` for the type — **no casing
assumption**, because the live data proved casing carries no meaning (`sNUSDAprPairProvider internal
provider;` would be missed by the existing `_STATE_VAR_TYPE_RE`, which requires `[A-Z]`). It captures
the NAME; the existing regex captures the TYPE and answers a different question. They coexist.

### US1/US2 — the redeclaration entry

Fire on the literal `Identifier already declared` (**text, not code** — research Decision 1). Within
the error block, extract the declared name from the underlined source lines. Both the primary and the
"previous declaration" block name the same identifier, so agreement is the signal.

- name parsed → authoritative, identifier-named instruction.
- name not confidently parsed → the generic-but-correct instruction (FR-004). A wrong specific name is
  worse than a right generic one.
- The instruction always offers **both** routes — use the inherited variable, or rename yours —
  because the colliding types can differ (live: `sNUSDAprPairProvider` vs `AprPairProvider`).

**Naming the declaring location (FR-003) comes from the compiler, not the scaffold.** The block reports
the file+line of BOTH colliding declarations; the one that is not under `POC_SUBDIR` is the base's. This
is authoritative, per-collision, and needs no scaffold parsing.

`_scaffold_base_name` is deliberately **not** used here. It is designed for a SINGLE scaffold file's
text — `read_scaffold` calls it per-file — whereas `_targeted_hints` receives `read_scaffold`'s output:
a rendered, multi-file blob. Applied to that blob it would compute leaves across all files and return
the last one, potentially naming the WRONG base — precisely the misleading specific claim FR-004 exists
to prevent.

### US3 — the gated member-not-found refinement

The existing entry keeps its structure. Before emitting today's text, check the new `scaffold`
parameter: if `_BASE_STATE_VAR_RE` — applied to the scaffold **after `_strip_comments`** — confirms the
missing member's name is declared there as a state variable, emit the refined instruction instead (drop
the `Y.` qualifier; it is the base's own, already-deployed variable). Otherwise — no scaffold, no match
— emit today's text **byte-identical** (FR-009).

Comments are stripped first because a commented-out declaration is not evidence, and this is the one
gate that must not misfire. The existing `_strip_comments` is reused; note that `_scaffold_base_name`
already strips before parsing while `scaffold_missing_types` does not — we follow the former.

Positive evidence is the gate. This makes the refinement strictly narrower than the condition the
entry already handles, so it cannot regress a case that works today.

**No ambiguity suppression.** An earlier draft would have withheld the refinement when the name looked
like a member of `Y`. That is incoherent: the 9582 error's own precondition is that the compiler has
already ruled the name "not found **or not visible**" on `Y`. If the scaffold declares it, the refined
instruction is correct regardless — and suppressing it would withhold a correct hint. Even the real
sub-case (a private member of `Y` sharing the name) resolves to "use the base's own".

### Threading

`_targeted_hints` gains `scaffold: str = ""`. The caller (`_process_finding`) already has `scaffold` in
scope — it reads it at the same site for `_poc_defects(..., scaffold_used=bool(scaffold))` — so this is
a one-line change. The default keeps every existing caller and test valid unchanged.

## Test Strategy

Two files, offline, synthetic fixtures only. Per research's fixture rule and memory
`feedback_no_target_code_in_agent`, fixtures reproduce the compiler output's **shape** with invented
names that resemble nothing in any audited target — the live log grounds the design and never enters
the repo.

`tests/unit/test_targeted_hints_9097.py` (US1/US2):

- redeclaration naming a concrete identifier → hint fires, names it.
- **live trap A**: lowercase-initial type → still recognized.
- **live trap B**: differing types → guidance offers the rename route.
- FR-003: declaring location named, and correctly distinguished from the PoC's own file.
- FR-003 degraded: location not derivable → hint still fires without it.
- FR-004: unparseable declaration → generic guidance, no invented name.
- US2: undeclared-identifier (7920) block → redeclaration hint absent, existing hint intact.
- US2: clean output → nothing.
- US2/FR-012: repeated trigger → de-duplicated once.
- US2: 9097 co-occurring with other errors → added alongside, none altered.

`tests/unit/test_targeted_hints_9582.py` (US3 + regression guards):

- FR-008: member-not-found whose name the synthetic scaffold declares → refined, unqualified-use hint.
- FR-008: name declared only inside a COMMENT in the scaffold → not evidence, no refinement.
- FR-009: name not in scaffold → today's text, byte-identical.
- FR-009: no scaffold → today's text, byte-identical.
- FR-009: called without the new argument at all → today's text, byte-identical (back-compat).

The byte-identical assertions are the regression guard on the one existing entry being touched.

## Complexity Tracking

None. The Constitution Check passes on every principle with no deviation to justify.
