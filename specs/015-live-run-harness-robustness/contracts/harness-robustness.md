# Contract: Live-Run Harness Robustness

Behavioral contracts for the three fixes (illustrative signatures, not final Python).

## US1 — Solidity extraction

```python
def _extract_solidity(text: str) -> str:
    """Return the real Solidity source from a model reply, or "" if none.
    - fenced block present            → its contents (happy path, byte-identical to today)
    - leading/trailing prose          → dropped; span from first Solidity token to last code
    - no Solidity token anywhere      → "" (caller fails the draft/fix; writes NO file)
    Solidity token = a line starting with // SPDX | pragma | import | contract |
    interface | library | abstract contract."""
```

| Guarantee | Behavior | SC |
|-----------|----------|-----|
| Clean extraction | prose-wrapped reply → PoC file is 0 prose lines, 0 fence markers | SC-001 |
| No empty write | code-free reply → failed draft/fix, no `.sol` written | SC-001 |
| Tool→marker fallback | tool round-trip yields no Solidity → retry that finding in marker mode | SC-002 |
| Happy path preserved | a clean fenced reply extracts identically to `_strip_fences` today | (FR-001) |

Call sites updated to use `_extract_solidity` and to treat `""` as failure:
`draft()`, `fix()`, `_generate_with_lookups`, `_generate_with_tool_calls`
(and the synth-scaffold generate at line ~705 stays behavior-compatible).

## US2 — proactive struct/enum grounding

```python
def expand_referenced_types(callable_api: str, index: SymbolIndex, *, budget: int = 2000) -> str:
    """Definitions of every struct/enum the callable_api references, nested one level,
    reusing _render_struct/_render_enum. Deduped, budget-bounded. "" if none/no index."""
```

| Guarantee | Behavior | SC |
|-----------|----------|-----|
| Fields up front | grounding includes referenced structs' full field lists (names+types) | SC-003 |
| Nested expansion | a struct field of struct/enum type is expanded one level | SC-003 |
| Enum values | referenced enums list their values | SC-003 |
| Lookup unchanged | `_render_lookup_response` still returns fields on demand (no regression) | SC-003 |

## US3 — compile-gated capture

```python
def _maybe_capture_lesson(store, log, fid, attempt, *, prev_error_sig, error_sig,
                          prev_fail_sig, real_pass, compiled,   # <-- compiled now passed in
                          prev_symptom, prev_code, code) -> None:
    """Capture ONLY when the attempt made real progress: compiled or real_pass AND the
    previous non-empty signature is now cleared. Never on a lateral/regression error
    change or a vacuous pass."""
```

| Guarantee | Behavior | SC |
|-----------|----------|-----|
| Real progress only | stuck→compiled/real_pass ⇒ exactly one candidate | SC-004 |
| No junk on regression | stuck→different error (not compiled) ⇒ zero candidates | SC-004 |
| Dedup preserved | one candidate per distinct signature (spec 014) | SC-005 |
| Gate preserved | promotion still out-of-band, human-gated (spec 014) | SC-005 |
