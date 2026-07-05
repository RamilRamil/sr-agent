# Data Model: AST-Grounded, Agentic Lookup for PoC Drafting

## Symbol

A named Solidity construct discovered by parsing the target project.

| Field | Type | Notes |
|---|---|---|
| `name` | string | The identifier as declared (e.g. `TCancelGuard`, `cancel`, `COOLDOWN_WORKER_ROLE`) |
| `kind` | `contract` \| `interface` \| `struct` \| `enum` \| `function` \| `modifier` \| `state_var` | |
| `contract` | string | The containing contract/interface name |
| `file` | path | Source file the symbol was parsed from |
| `definition` | string | The REAL, complete rendering — for `struct`: every field name + type; for `function`: full signature + every modifier invocation; for `enum`: every value; for `state_var`: its declared type + visibility |
| `modifiers` | list[string] | Only for `kind == function`; each real modifier invocation (e.g. `onlyUser(user)`) — the CALLER REQUIREMENT data |

**Validation rule**: `definition` MUST be derived from the parsed AST, never
hand-assembled from a text pattern — this is what makes `Symbol` trustworthy as
ground truth (FR-002).

## SymbolIndex

The queryable structure built once per target project, from parsing every `.sol` file
reachable from the finding's scope (or the whole project, per implementation choice in
tasks).

| Field | Type | Notes |
|---|---|---|
| `symbols` | dict[name → list[Symbol]] | Multiple entries per name are real (overloads, same name in different contracts) — see research.md R3 |
| `unparsed_files` | list[path] | Files that failed to parse; logged, not fatal (research.md R8) |

**Operations**:
- `lookup(name: str) -> list[Symbol]` — returns every real match; empty list means
  genuinely not found (FR-008 — never fabricated).
- `build(project_root: Path) -> SymbolIndex` — parses every `.sol` file under the
  project, skipping ones that fail (R8).

**Validation rule**: `lookup()` for a name with zero real matches MUST return an empty
list, distinguishable from "the index itself failed" (which should raise/log
separately, not silently look like "not found" — these are different failure modes and
must not be conflated).

## Lookup Request

An in-flight request the model makes during a single draft/fix turn.

| Field | Type | Notes |
|---|---|---|
| `symbol_name` | string | Exactly as the model wrote it in its `LOOKUP: <name>` line |
| `attempt` | int | Which draft/fix attempt this occurred in (for the run log) |
| `resolved` | bool | Whether `SymbolIndex.lookup()` returned ≥1 match |
| `match_count` | int | How many `Symbol`s were returned (for logging/ambiguity visibility) |

**Validation rule**: every `Lookup Request` is logged as its own JSONL event
(`event: "lookup"`) regardless of whether it resolved — satisfies SC-004's
observability requirement.

## Lookup Budget

The bound on Lookup Requests per PoC attempt (research.md R4).

| Field | Type | Notes |
|---|---|---|
| `max_per_attempt` | int | Default 3; CLI-configurable |
| `used` | int | Reset at the start of each attempt |

**Validation rule**: once `used == max_per_attempt`, no further lookup round-trip is
performed for that attempt — the model's next output is treated as final regardless of
whether it contains another `LOOKUP:` line (satisfies FR-004 / the runaway-loop edge
case).

## Relationships

```
SymbolIndex ──built once from──> target project's .sol files (via solidity-parser)
Lookup Request ──resolved by──> SymbolIndex.lookup(symbol_name) ──returns──> Symbol[]
Lookup Budget ──bounds──> how many Lookup Requests one PoC attempt may make
```

No persistent storage — `SymbolIndex` lives in-process for the duration of one harness
run; `Lookup Request`/`Lookup Budget` state lives for the duration of one PoC attempt.
Both are logged (not stored) via the harness's existing JSONL progress log.
