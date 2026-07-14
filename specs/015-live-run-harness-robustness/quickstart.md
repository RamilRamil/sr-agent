# Quickstart: Live-Run Harness Robustness

All offline. Each maps to a user story and its SCs.

## 1. Clean Solidity extraction + no empty PoC (US1 / SC-001, SC-002)

```python
from scripts.poc_queue_runner import _extract_solidity

# prose-wrapped → only the Solidity
r = "Looking at the errors, let me fix it:\n\n```solidity\n// SPDX-License-Identifier: MIT\npragma solidity ^0.8.28;\ncontract P {}\n```\nThat should work."
out = _extract_solidity(r)
assert out.startswith("// SPDX") and out.rstrip().endswith("}")
assert "Looking at" not in out and "```" not in out

# prose-only → "" (caller fails the draft, writes no file)
assert _extract_solidity("Let me analyze what's wrong with the previous attempt.") == ""
```

Integration (spec-009 fake harness): a scripted draft reply with leading prose → the written
PoC is clean Solidity; a code-free reply → outcome is a failed draft (no `.sol` written); a
tool-mode reply that returns no code → the finding retries under the marker protocol.

## 2. Struct/enum fields grounded up front (US2 / SC-003)

```python
from scripts.solidity_index import SymbolIndex, expand_referenced_types
# real API: build_from_source(source: str)  (single string) — NOT build_from_sources({...})
idx = SymbolIndex.build_from_source(
    "interface I { enum E { X, Y } struct S { uint32 a; E e; } function f(S calldata s) external; }")
g = expand_referenced_types("function f(S calldata s) external;", idx)
assert "struct S" in g and "uint32 a" in g          # referenced struct expanded
assert "enum E" in g and "X" in g                    # nested enum expanded one level
```

## 3. Compile-gated capture (US3 / SC-004, SC-005)

```python
# stuck (compile error) → next attempt compiles ⇒ exactly ONE lesson candidate
# stuck → next attempt has a DIFFERENT error (not compiled) ⇒ ZERO candidates
pytest tests/unit/test_capture_trigger.py -q
```

Driven through the spec-009 harness: a scripted `[compile-error] → [compiled]` transition
captures one candidate; a `[compile-error A] → [compile-error B]` (regression/lateral, still
failing) captures none. Dedup + human gate behave exactly as spec 014.

## 4. Full offline validation (all SCs)

```bash
pytest tests/unit/test_solidity_extract.py tests/unit/test_capture_trigger.py \
       tests/unit/test_struct_grounding.py \
       tests/integration/test_poc_extract_prose.py \
       tests/integration/test_tool_empty_fallback.py -q
# then the full suite stays green, no new dependency:
pytest tests/unit tests/integration tests/architecture tests/security tests/frontend -q
```
