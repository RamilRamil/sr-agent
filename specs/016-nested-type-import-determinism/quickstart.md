# Quickstart: Nested-Type Import Determinism

All offline. Each maps to a user story and its SCs.

## 1. Mechanical guard rewrites a nested named-import (US1 / SC-001, SC-002)

```python
from scripts.solidity_index import SymbolIndex
from scripts.poc_queue_runner import _fix_nested_type_imports

idx = SymbolIndex.build_from_source(
    'interface I { struct S { uint32 a; } function f(S calldata s) external; }')
file_map = "I: ../../contracts/I.sol"

# the real case (H1): the body uses the nested type BARE
poc = ('import { I } from "../../contracts/I.sol";\n'
       'import { S } from "../../contracts/I.sol";\n'
       'contract P { function t() public { S memory x = S({a: 1}); } }')
out, changed = _fix_nested_type_imports(poc, idx, file_map)
assert changed
assert 'import { S }' not in out          # nested named-import removed
assert 'import { I }' in out              # container still imported
assert 'I.S memory x = I.S({a: 1})' in out  # bare uses rewritten → Container.Type (compiles)
assert ' S memory' not in out and 'S({' not in out.replace('I.S({', '')  # no bare S left

# idempotent
out2, changed2 = _fix_nested_type_imports(out, idx, file_map)
assert changed2 is False and out2 == out

# no false rewrite of a top-level type
top = 'import { I } from "../../contracts/I.sol";\ncontract P {}'
assert _fix_nested_type_imports(top, idx, file_map) == (top, False)
```

## 2. Grounding note for a nested type (US2 / SC-003)

```python
from scripts.solidity_index import SymbolIndex, expand_referenced_types
idx = SymbolIndex.build_from_source(
    'interface I { struct S { uint32 a; } function f(S calldata s) external; }')
g = expand_referenced_types("function f(S calldata s) external;", idx)
assert "struct S" in g and "uint32 a" in g          # fields (spec 015)
assert "nested inside" in g and "I.S" in g           # NEW: nested-reference note
```

## 3. Authoritative 2904 hint (US3 / SC-004)

```python
from scripts.solidity_index import SymbolIndex
from scripts.poc_queue_runner import _targeted_hints
idx = SymbolIndex.build_from_source(
    'interface I { struct S { uint32 a; } function f(S calldata s) external; }')
err = 'Error (2904): Declaration "S" not found in "I.sol" (referenced as "../../I.sol")'
h = _targeted_hints(err, callable_api="", file_map="", code="", symbol_index=idx)
assert "nested" in h and "I.S" in h                  # container + Container.X form
# an invented name gets no nested-type hint
assert "Bogus" not in _targeted_hints(
    'Declaration "Bogus" not found', "", "", "", idx)
```

## 4. Full offline validation (all SCs)

```bash
pytest tests/unit/test_nested_import_guard.py tests/unit/test_nested_container.py \
       tests/unit/test_struct_grounding.py tests/unit/test_targeted_hints_2904.py -q
# then the full suite stays green, no new dependency:
pytest tests/unit tests/integration tests/architecture tests/security tests/frontend -q
```

## 5. (Opportunistic) live re-run (SC-006)

Re-run H-01 (`--lookup-protocol marker --image sr-agent-foundry:strata-bb`); the `Error 2904`
nested-import stall should no longer recur — H-01 advances past it. Not required for merge.
