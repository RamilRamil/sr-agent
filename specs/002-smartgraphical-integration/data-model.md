# Data Model: SmartGraphical Integration

## Consumed entities (from SmartGraphical JSON)

### SmartGraphical Finding (input)
Fields read from each finding in the engine's `auditor json` output:

| Field | Meaning |
|---|---|
| `rule_id` | rule slug, e.g. `withdraw_check`, `read_only_oracle_reentrancy` |
| `task_id` | task identifier (`1`..`15`, `taint`) |
| `title` | human title |
| `category` | `dataflow` / `state` / `ordering` / `economics` / `naming` / ... |
| `portability` | `portable` / `portable_with_adapter` |
| `confidence` | `low` / `medium` / `high` |
| `message` | finding description |
| `remediation_hint` | fix guidance |
| `evidences[]` | `{ type_name, function_name, statement, source_statement, line_number, confidence_reason }` |

### SmartGraphical Graph (input)
From the `{ nodes, edges }` payload (`model_graph_to_dict`):

| Edge `kind` | Used for |
|---|---|
| `state_to_function_read` | function reads state entity |
| `state_to_function_write` | function writes state entity |
| `function_to_function` | caller → callee (same contract) |
| `cross_type_call` | child → parent function (inheritance) |
| `cross_type_state_read/write` | parent state, child function |
| `function_to_system` / `function_to_object` | external/system call surface |
| `function_to_event` | emits (ignored for SIG) |

Node groups: `type`, `function`, `modifier`, `state`, `event`, `external`. Each node has a stable
id (`function:<Type>.<fn>`, `state:<Type>.<var>`, …) and (in bundles) a `source_file`.

## Produced / extended SR-agent entities

### Finding (existing model, reused)
A SmartGraphical finding maps to a `Finding`:

| Finding field | Source |
|---|---|
| `finding_id` | `SG-<NNN>` generated per audit |
| `location` | `<file>:<line>` from first evidence (audit-root-relative file) |
| `function_name` | evidence `function_name` (or `unknown`) |
| `severity` | from `confidence` (R2) |
| `bastet_tag` | from `rule_id`/`category` lookup, else `None` (R3) |
| `status` | unconfirmed default (US3) |

Stored finding **payload** (the dict in the memory record) additionally carries:
- `notes` = `message` + " — " + `remediation_hint` (sanitized)
- `notes_flags` = sanitizer flags
- `engine` = `"smartgraphical"` (R6, new attribution field)
- `rule_id`, `category`, `confidence` (kept verbatim for the report)

Provenance: written via `episodic.write` with `source_type=tool_output` (trust 3).

### StateInterferenceGraph (existing, new builder)
`build_sig_from_smartgraphical(graph_json) -> StateInterferenceGraph`:
- `FunctionNode.reads` ← targets of `state_to_function_read` (+ `cross_type_state_read`)
- `FunctionNode.writes` ← targets of `state_to_function_write` (+ `cross_type_state_write`)
- `FunctionNode.has_external_call` ← function has any `function_to_system`/`function_to_object`
  edge (or non-empty external calls)
- call adjacency ← `function_to_function` + `cross_type_call`
`interferes()` / `can_reenter()` unchanged. Function keys are the bare function name to match
finding locations (`file:function`), consistent with the regex SIG.

## Validation rules
- A finding with no resolvable location still ingests (location = `<file>` only).
- Invalid/garbled JSON → zero findings for that file (best-effort, FR-004).
- An unmapped `rule_id` → tag `None` (never a guessed tag) (FR-003).
- `engine` field is informational; it does not affect trust (trust is `source_type`).

## State transitions (finding lifecycle, unchanged)
```
ingested (tool_output, unconfirmed)
   → PoC written + run in sandbox
       → poc passed  → confirmed
       → poc failed  → unverified / false_positive
       → mock stub   → mock_review
```
SmartGraphical never sets a status beyond the unconfirmed default (US3 invariant).
