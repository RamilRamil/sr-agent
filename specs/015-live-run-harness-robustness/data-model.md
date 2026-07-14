# Data Model: Live-Run Harness Robustness

No persisted entities — this feature transforms in-flight strings and tightens one
predicate. The "entities" are the transient shapes the three fixes operate on.

## Model reply → extracted Solidity (US1)

```text
reply (str)  ──_extract_solidity──▶  solidity (str)   # "" ⇒ no code
```

| Input shape | Output |
|-------------|--------|
| clean fenced block ```` ```solidity … ``` ```` | the block contents (happy path, unchanged) |
| leading prose + fenced block | the block contents (prose dropped) |
| leading prose + bare Solidity (no fence) | span from first Solidity token → last code line |
| Solidity + trailing prose / stray ``` | trailing non-Solidity dropped |
| prose-only / empty / tool-noise only | `""` → caller treats as **failed draft/fix** (no file written) |

**Solidity-token anchor set**: a line whose stripped form starts with one of
`// SPDX`, `pragma`, `import`, `contract`, `interface`, `library`, `abstract contract`.
The extracted source is the slice from the first such line to the last line that is not
trailing prose (a closing fence or a prose paragraph after the last `}`), reusing the
existing fence-strip for the fenced happy path.

## callable_api → grounding struct/enum expansion (US2)

```text
callable_api (str) + SymbolIndex  ──expand_referenced_types──▶  definitions (str)
```

- Scan the `callable_api` signatures for type identifiers (parameter/return types).
- For each identifier the index knows as a `struct` or `enum`, emit its `definition`
  (`_render_struct`/`_render_enum`, which already list members).
- For a struct field whose type is itself a known struct/enum, expand that too — **one
  level** of nesting (e.g. `TExitUpperBounds { … TExitParams r0 … }` ⇒ also emit
  `TExitParams { … }`).
- Bound the output (a char budget) so grounding doesn't bloat; dedup by type name.
- Purely additive to the existing grounding text; on-demand lookup response is untouched.

## Capture transition predicate (US3)

The spec-014 `_maybe_capture_lesson` gains verdict awareness:

| prev signature | current attempt verdict | current signature | capture? |
|----------------|-------------------------|-------------------|----------|
| non-empty (stuck) | **compiled or real_pass** | (prev cleared) | **YES — 1 candidate** |
| non-empty (stuck) | still failing | different error | **NO** (lateral/regression) |
| non-empty (stuck) | still failing | same error | NO (stall, unchanged) |
| non-empty (stuck) | vacuous_pass (empty test) | — | **NO** (not real progress) |
| empty | any | — | NO (nothing to resolve) |

Dedup-by-`sig_id` and human-gated promotion (spec 014) are unchanged — only the trigger
now requires a genuinely-better verdict, not merely "prev signature absent".
