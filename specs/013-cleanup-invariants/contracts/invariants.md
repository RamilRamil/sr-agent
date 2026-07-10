# Contract: the two architecture invariants

## `tests/architecture/test_source_type_hierarchy.py` (US2)

Imports the real rank map from `sr_agent/models/memory.py` and asserts, at minimum:

```
rank[human_input]        > rank[tool_output]
rank[tool_output]        > rank[external_llm_output]
rank[external_llm_output] == rank[human_relayed_tool]
rank[external_llm_output] > rank[llm_inference]
```

**Invariant**: Principle I's ordering (model/relay output never outranks human input or
tool output) is pinned; a reorder fails the test (FR-004). Includes an assertion that a
simulated flip (e.g. a copy of the map with `external_llm_output` raised) would violate
the relation — documenting the failure mode.

## `tests/architecture/test_harness_sandbox_only.py` (US3)

`ast`-parses `scripts/poc_queue_runner.py` and collects every `subprocess.run(...)` /
`subprocess.Popen(...)` call node; for each, inspects the command argument (the first
list literal) and asserts its first element is the literal `"git"`.

```
for call in subprocess_calls(harness_ast):
    cmd0 = first_list_element(call.args[0])
    assert cmd0 == "git", f"harness runs a non-git subprocess: {cmd0!r}"
```

**Invariant**: PoC/forge code executes only through `run_tests` (sandbox-backed); the
harness's direct subprocesses are benign git (FR-005). A hypothetical
`subprocess.run(["forge", "test", …])` fails the test. Includes a negative check on a
synthetic AST snippet (`subprocess.run(["forge","test"])`) to prove the guard catches it.
