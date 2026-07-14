# Contract: Nested-Type Import Determinism

Behavioral contracts (illustrative signatures, not final Python).

## Helper — `SymbolIndex.nested_container`

```python
def nested_container(self, name: str) -> str | None:
    """The containing contract/interface iff `name` is UNAMBIGUOUSLY a nested struct/enum
    (≥1 nested match, no top-level match, single container); else None."""
```

| Guarantee | Behavior | SC |
|-----------|----------|-----|
| Nested detected | a struct/enum with one non-empty `contract` → returns it | SC-001 |
| Top-level excluded | any top-level match → `None` | SC-001 |
| Ambiguous excluded | 2+ distinct containers → `None` | SC-001 |
| Unknown excluded | not in index / not struct-enum → `None` | SC-001 |

## US1 — `_fix_nested_type_imports(code, symbol_index, file_map) -> (code, changed)`

| Guarantee | Behavior | SC |
|-----------|----------|-----|
| Rewrite nested import | `import { Nested } from "…"` → dropped, container imported | SC-001 |
| Rewrite bare uses (H1) | bare `Nested` in the body → `Container.Nested` (already-qualified untouched) — required so removing the import actually compiles | SC-001 |
| Keep top-level | mixed line → only nested names removed | SC-001 |
| No false rewrite | top-level/unknown/library imports + already-qualified uses byte-unchanged | SC-001 |
| Idempotent | second run → `changed=False`, identical output | SC-002 |
| Logged | on change, `postfix_nested_import` event | (FR-004) |
| Applied | after draft + every fix (with the other guards) | (FR-002) |

## US2 — grounding note (`expand_referenced_types`)

| Guarantee | Behavior | SC |
|-----------|----------|-----|
| Nested note | expanded type with non-empty `contract` → fields + nested-reference note | SC-003 |
| Top-level clean | `contract == ""` → fields, no note | SC-003 |

## US3 — `_targeted_hints(forge_output, callable_api, file_map, code, symbol_index)`

| Guarantee | Behavior | SC |
|-----------|----------|-----|
| Nested 2904 → hint | `Declaration "X" not found …`, X nested → authoritative `Container.X` fix | SC-004 |
| Unknown → no hint | X not index-known-nested → no nested-type hint | SC-004 |

## Invariants (all layers)

- Only names `nested_container` resolves are ever touched (FR-003 determinism boundary).
- No kernel invariant / DATA-wrap / trust hierarchy / promotion gate / retrieval change (FR-008).
- Offline-only; no new dependency (FR-007).
