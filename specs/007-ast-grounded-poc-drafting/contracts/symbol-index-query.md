# Contract: SymbolIndex Query API

The programmatic interface `SymbolIndex` exposes to the harness (used both by the
lookup protocol and, eventually per research.md R6, by a re-platformed static-grounding
renderer).

## Build

```python
index = SymbolIndex.build(project_root: Path) -> SymbolIndex
```

Parses every `.sol` file reachable under `project_root` via `solidity-parser`.
Files that fail to parse are skipped and recorded in `index.unparsed_files`
(research.md R8) — building never raises for a single bad file.

## Query

```python
index.lookup(name: str) -> list[Symbol]
```

- Returns every real match across every parsed file (possibly 0, 1, or many —
  research.md R3). Never guesses a single "best" match when there is genuine ambiguity.
- An empty list means the symbol genuinely does not exist anywhere in the parsed
  project (FR-008) — this is a DIFFERENT signal from "the index failed to build",
  which is a distinct, separately-logged condition (an empty `unparsed_files`-driven
  gap vs. a name that simply isn't declared anywhere).
- Lookup is by exact name match (case-sensitive, matching Solidity's own identifier
  rules) — no fuzzy matching in this pass (would reintroduce the "guessed" failure
  mode this feature exists to remove).

## Rendering a match for the model

```python
symbol.definition -> str
```

Already-formatted, real, complete text — no further transformation needed before
inserting into a `[DATA]` block per the lookup-protocol contract. For a `struct`
Symbol, this is every field name + type; for a `function` Symbol, the full signature
+ every real modifier invocation (the same CALLER REQUIREMENT information the
existing `callable_api` annotations already provide, sourced correctly this time from
the AST rather than a regex over the tail of a signature string).

## Failure modes and their signals

| Situation | Signal |
|---|---|
| Symbol genuinely doesn't exist | `lookup()` returns `[]` |
| Symbol exists but is ambiguous (2+ matches) | `lookup()` returns all matches, each tagged with its contract |
| A specific file failed to parse | recorded in `index.unparsed_files`; symbols that would live there are indistinguishable from "not found" to `lookup()` (a known, accepted limitation — research.md R8) |
| The whole build failed catastrophically | this MUST NOT happen silently — `build()` only skips per-file, so a total failure indicates a bug in `SymbolIndex` itself, not a normal degraded state, and should surface as an exception during development/testing, not swallowed |
