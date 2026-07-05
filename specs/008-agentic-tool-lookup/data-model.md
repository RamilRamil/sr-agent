# Data Model: Native Agentic Tool-Calling for PoC Symbol Lookup

This feature adds entities alongside spec 007's `Symbol`/`SymbolIndex`/`Lookup
Budget` (unchanged — see [007's data-model.md](../007-ast-grounded-poc-drafting/data-model.md)).
Only the REQUEST/RESPONSE transport is new here.

## Tool Call

A model-issued, structured request to invoke `lookup_symbol`, as returned by
Ollama's `/api/chat` in `message.tool_calls`.

| Field | Type | Notes |
|---|---|---|
| `name` | string | Always `"lookup_symbol"` in this feature (single-tool, per spec's out-of-scope) |
| `arguments.name` | string | The symbol name the model wants resolved — semantically identical to spec 007's `Lookup Request.symbol_name` |

**Validation rule**: a Tool Call missing or malforming `arguments.name` is treated
as an unresolved lookup (logged, counted against budget) — never a crash (edge
case in spec.md).

## Tool Result

The harness's structured response to one Tool Call, appended to the conversation
as a `{"role": "tool", ...}` message.

| Field | Type | Notes |
|---|---|---|
| `symbol_name` | string | Echoes the requested name |
| `matches` | list[Symbol] | Resolved via the EXISTING, unchanged `SymbolIndex.lookup()` (spec 007) — same qualified-name fallback, same never-fabricate-on-miss |
| `rendered` | string | JSON-serializable content for the `tool` message — semantically the same information spec 007's `_render_lookup_response()` produces for the text-marker protocol, just delivered as a structured message instead of an appended `[DATA]` block |

**Validation rule**: `rendered` MUST carry the same information spec 007's
text-marker path renders for the same `matches` (including the nested-type
import NOTE for struct/enum matches) — SC-002 requires byte-identical resolution
behavior across both protocols, not just equivalent-enough.

## Protocol Mode

Which lookup protocol a given attempt used — recorded for observability and the
optional live-comparison (User Story 4), not a persistent/operator-facing setting
beyond the `--lookup-protocol` override.

| Field | Type | Notes |
|---|---|---|
| `value` | `tool` \| `marker` | `tool` = native Ollama tool-calling (this feature); `marker` = spec 007's existing `LOOKUP:` text-marker protocol |
| `source` | `detected` \| `forced` | Whether the mode came from capability auto-detection or an explicit `--lookup-protocol` override |

**Validation rule**: `Protocol Mode` selection happens ONCE per harness run (at
the same point `warm()`/`ready()` already execute), not per-attempt or
mid-attempt (research.md R4 — no mid-run downgrade).

## Relationships

```
LocalClient.supports_tools() ──detected once at run start──> Protocol Mode
Protocol Mode == "tool"  ──> native round-trip: Tool Call ──resolved by──> SymbolIndex.lookup()
                                                                          (UNCHANGED from spec 007)
                                              ──produces──> Tool Result ──appended as──> {"role":"tool"} message
Protocol Mode == "marker" ──> spec 007's existing _generate_with_lookups() / LOOKUP: path, untouched

Both paths ──log──> the SAME {"event": "lookup", "finding_id", "attempt", "symbol",
                              "resolved", "match_count"} shape (FR-006)
```

No persistent storage — `Protocol Mode` is decided once per harness run and held
in-process (same lifetime as spec 007's `SymbolIndex`); `Tool Call`/`Tool Result`
exist only for the duration of one draft/fix attempt's round-trip, same as spec
007's `Lookup Request`/`Lookup Budget`. Both protocols share the identical JSONL
progress log.
