# Contract: Agentic Lookup Protocol

The text-marker protocol (research.md R2) between the harness and the local model
during PoC drafting/repair.

## Request (model → harness)

The model, when unsure of a symbol's real definition, emits a line matching:

```
LOOKUP: <symbol name>
```

as part of (or as the entirety of) its response. Exactly one symbol per line;
multiple lines request multiple lookups (each counted against the Lookup Budget
independently, in order, up to the budget).

**Rules for the model** (stated in the draft/fix prompt):
- Only request a symbol if genuinely unsure of its real fields/signature/modifiers —
  the file map, callable_api, scaffold, and example already answer most cases.
- A `LOOKUP:` line does not need to be the model's entire output; it may appear
  alongside partial reasoning, but the harness treats its PRESENCE as "not yet a final
  answer" and will re-prompt rather than accept that turn's Solidity code as final.

## Response (harness → model)

For each `LOOKUP: <name>` line detected (up to the remaining Lookup Budget):

```
[DATA] <name> resolved to N definition(s):

// <contract> (<kind>)
<the real Symbol.definition text>

...
```

or, if `SymbolIndex.lookup(name)` returns zero matches:

```
[DATA] <name>: NOT FOUND in the target project. This name does not exist — do not
use it. Re-check the spelling, or use only symbols already shown in this prompt.
```

This is appended to a follow-up turn's context (matching the project's DATA-wrapping
convention for anything that re-enters model context — see `orchestrator/context.py`'s
`wrap_data`, applied here in spirit even though this harness is standalone from the
kernel).

## Budget exhaustion

Once the Lookup Budget for the current attempt is exhausted, the harness does NOT
perform another lookup round-trip: the model's next generated output (even if it
contains a `LOOKUP:` line) is treated as the final PoC source for that attempt.

## Logging

Every request (resolved or not) is logged as:

```json
{"event": "lookup", "finding_id": "...", "attempt": N, "symbol": "<name>",
 "resolved": true|false, "match_count": M}
```

## Interaction with existing static grounding

The lookup protocol is ADDITIVE (research.md R6): the file map, callable_api, scaffold,
and few-shot example are still included in the initial draft prompt exactly as before.
`LOOKUP:` is presented as an escape hatch for symbols NOT already covered by those
blocks (e.g. a struct's fields, an enum's values) — the prompt should say so explicitly
so the model doesn't waste its budget re-asking about something already shown.
