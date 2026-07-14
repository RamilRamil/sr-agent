# Data Model: Nested-Type Import Determinism

No persisted entities — transient string transforms + one index predicate. The "model" is
the detection rule and the guard's rewrite behavior.

## `SymbolIndex.nested_container(name) -> str | None`

The determinism source, read from existing `Symbol` data (no new parsing):

| index knowledge of `name` | result |
|---------------------------|--------|
| exactly one struct/enum match with non-empty `contract`, no top-level match | that `contract` (nested) |
| a top-level match exists (any `contract == ""`) | `None` (not treated as nested) |
| ≥2 distinct nested containers (ambiguous) | `None` (conservative) |
| not a struct/enum, or unknown | `None` |

## US1 guard: `_fix_nested_type_imports(code, symbol_index, file_map) -> (code, changed)`

Per `import { A, B, … } from "path";` line:

```text
names → { nested: [n for n in names if nested_container(n)],
          keep:   [n for n in names if not nested_container(n)] }
if nested is empty            → line unchanged
elif keep is empty            → drop the whole import line
else                          → rewrite to `import { <keep> } from "path";`
for each nested name's container C (deduped):
    if no existing import of C → add `import { C } from "<container_path>";`
       where container_path = _path_for(file_map, C)  OR (fallback, L1) the "path" of the
       named-import line the nested name was removed from (the container's own file)
for each removed nested name X (container C):
    rewrite BARE uses of X in the body → `C.X`
       regex: word-boundary X NOT preceded by `.` (skip already-qualified `C.X`,
       field accesses `foo.X`) and NOT on an import line → prevents double-qualification
changed = any import rewritten/dropped/added OR any bare reference rewritten
```

- **Untouched**: `@openzeppelin/…`, `forge-std/…`, library/remapped imports; names the index
  doesn't know; aliased imports (`X as Y`); top-level types; already-qualified uses (`C.X`).
- **Why the bare-rewrite is required** (H1): the model named-imports these types AND uses them
  bare (`TExitUpperBounds memory b = TExitUpperBounds({…})`); removing only the import →
  `undefined identifier`. The rewrite makes the guard genuinely unblock.
- **Idempotent**: after the pass there is no nested named-import and every use is qualified
  (`C.X`, skipped by the not-preceded-by-`.` rule) → a second run yields `changed == False`
  and identical output.
- **Applied**: after `draft()` and after every `fix()` (with `_fix_setup_override` /
  `_fix_import_paths`); logs `postfix_nested_import` when `changed`.

## US2 grounding note (in `expand_referenced_types`)

For each expanded type whose `Symbol.contract` is non-empty, append after its definition the
canonical note (identical wording to `_render_lookup_response`):

```text
// NOTE: <X> is nested inside <Container> — do NOT `import { <X> } from ...;`.
// Import <Container> and reference the type as <Container>.<X>.
```
A top-level type (`contract == ""`) gets its fields with **no** note.

## US3 hint (in `_targeted_hints`, now taking `symbol_index`)

For each `Declaration "(\w+)" not found` in the forge output:

| `nested_container(X)` | hint |
|-----------------------|------|
| `Container` | authoritative: "`X` is nested in `Container` — remove `import { X } from …;`, reference it as `Container.X` (import `Container` if needed)." |
| `None` | no nested-type hint (existing 6275 / "not a real symbol" handling applies) |

## Consistency

The lookup response (`_render_lookup_response`), the proactive grounding note, and the repair
hint all use the **same** "import the container, use `Container.X`, don't named-import"
wording — the model meets one consistent instruction wherever it encounters a nested type,
and the guard enforces it regardless.
