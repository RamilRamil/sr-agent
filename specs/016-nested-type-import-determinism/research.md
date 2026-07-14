# Research: Nested-Type Import Determinism

Phase 0. Grounded in the harness's existing mechanical-guard pattern and a direct probe of
the symbol index against the live target.

## R1 — The index already flags nested types (probe-confirmed) — determinism source

**Decision**: Detect a nested type via `SymbolIndex.lookup(name)` → a `Symbol` whose
`kind ∈ {struct, enum}` and whose `contract` is non-empty; `contract` is the container name.

**Rationale**: A direct probe against the live target confirmed
`lookup("TExitUpperBounds")` returns `Symbol(kind="struct", contract="ISharesCooldown",
definition="struct TExitUpperBounds { uint32 p0; uint32 p1; TExitParams r0; r1; r2; }")`.
A top-level type has `contract == ""`. So the "is this a nested type, and what is its
container?" question the whole feature turns on is already answered by the index — no new
parsing. A tiny helper `SymbolIndex.nested_container(name) -> str | None` (returns the
container iff exactly one nested match and no top-level match; `None` otherwise) makes the
ambiguity rule explicit and reusable by all three layers.

**Alternatives considered**:
- *Regex the target source for `struct X` inside a contract* — rejected: re-implements what
  the AST index already knows, and is exactly the fragile pattern spec 007 replaced.

## R2 — US1 guard: mirror `_fix_setup_override`/`_fix_import_paths`, line-by-line, idempotent

**Decision**: `_fix_nested_type_imports(code, symbol_index, file_map) -> (code, changed)`,
applied right where `_fix_setup_override` and `_fix_import_paths` already run (after draft,
after every fix). For each `import { A, B, … } from "path";` line: partition the names into
nested (via `nested_container`) and the rest; drop the nested names (if none remain, drop the
whole line; else keep the remaining named-import); collect each nested name's container. Then
ensure each container is imported — reuse `_path_for(file_map, container)` for the real path
(the same source `_targeted_hints`' import rule uses), adding `import { Container } from
"<path>";` only if no import of that container already exists. Log `postfix_nested_import`
when changed.

**Rationale**: The mechanical-guard pattern (`(code, changed)`, line-by-line so non-import
lines are untouched, applied post-generation) already exists for exactly this class of
"model keeps making a mechanical mistake" problem. Nested-import is mechanically detectable
and mechanically fixable; the guard makes the fix model-independent. Idempotency falls out:
after the rewrite there is no nested named-import left, so a second pass changes nothing.

**REQUIRED companion — rewrite bare references too (corrected from an earlier deferral).**
Verified against the real quarantined PoC: the model named-imports the nested types AND uses
them **bare** in the body (`TExitUpperBounds memory bounds = TExitUpperBounds({…})`,
`TExitParams({…})` ×3) — it only dot-qualifies *some* types (`ISharesCooldown.TCancelGuard`),
not these. So removing the named-import alone would trade `Error 2904` for an
`undefined identifier` error — the guard would NOT unblock. Therefore the guard MUST also
rewrite bare references of each removed nested type `X` → `Container.X` in the body:
word-boundary match, **skipping** occurrences already qualified (preceded by `.`, e.g.
`ISharesCooldown.X` or a field access) and the import lines themselves. This makes the guard
genuinely model-independent. Safe because the index confirms `X` is a type (not a local), and
the skip-if-already-qualified rule prevents double-qualification / idempotency breakage.

**Alternatives considered**:
- *Fix only the import, leave references* — REJECTED (the correction above): the named-import
  case is exactly when the body uses the bare name, so this produces `undefined identifier`
  and fails to unblock.
- *A guard with no index (pure regex on "types that look nested")* — rejected: no way to
  know nesting without the index; would false-rewrite top-level types.

## R3 — Ambiguity & safety: only touch names the index unambiguously knows as nested

**Decision**: `nested_container(name)` returns a container only when the index has ≥1 nested
match AND no top-level match for that name; otherwise `None` (leave alone). The guard never
touches `@openzeppelin/…`/`forge-std/…`/library imports, and never rewrites a name the index
doesn't know (that stays with the existing "not a real symbol" handling). Aliased imports
(`import { X as Y }`) are left unchanged in v1 (rare; a partial rewrite risk).

**Rationale**: The determinism boundary must be tight (FR-003, no false rewrites). An
ambiguous name (both top-level and nested somewhere) is precisely where a mechanical rewrite
could break correct code, so it is excluded.

## R4 — US2 grounding note & US3 hint reuse the existing nested-note wording

**Decision**: US2 — in `expand_referenced_types`, for a picked type whose `Symbol.contract`
is non-empty, append the same nested-reference note `_render_lookup_response` already emits
("`X` is nested inside `Container` — do NOT `import { X } from …;`; import `Container` and
reference it as `Container.X`"). US3 — `_targeted_hints` gains a `symbol_index` parameter and
a rule: for each `Declaration "(\w+)" not found` in the forge output, if `nested_container`
resolves it, emit the authoritative `Container.X` fix; otherwise emit nothing (the existing
6275/"not a real file" handling covers genuinely-invented names). The 2904 message shape
(`Declaration "X" not found in "…" (referenced as "…")`) is matched on the `Declaration "X"
not found` prefix.

**Rationale**: One canonical wording for the nested-type guidance across the lookup response,
the proactive grounding, and the repair hint — the model sees a consistent instruction
wherever it encounters the type. Passing `symbol_index` into `_targeted_hints` is the minimal
change (the index is already in scope at the call site in `_process_finding`).

## R5 — Validation is fully offline

**Decision**: US1 via `SymbolIndex.build_from_source` fixtures + direct `_fix_nested_type_imports`
calls (nested → rewritten; top-level → unchanged; mixed → partial; idempotent). US2 via
`expand_referenced_types` on a nested-struct fixture asserting the note. US3 via
`_targeted_hints` on a synthetic 2904 string with the index (nested → authoritative hint;
unknown → none). No model, Docker, network; no new dependency. SC-006 (live H-01 stall gone)
is validated opportunistically on a re-run, not required for merge.

**Rationale**: The fixtures and the fake harness already exist; these are ordinary additions.
