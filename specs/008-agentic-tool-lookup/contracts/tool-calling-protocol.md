# Contract: Native Tool-Calling Lookup Protocol

The structured tool-call protocol between the harness and the local model during
PoC drafting/repair, for models/hosts detected as tool-capable (see
`protocol-selection.md`). Semantically equivalent to spec 007's `LOOKUP:`
text-marker protocol ([007's lookup-protocol.md](../../007-ast-grounded-poc-drafting/contracts/lookup-protocol.md))
— only the transport differs.

## Tool declaration (harness → model, once per chat request)

```json
{
  "type": "function",
  "function": {
    "name": "lookup_symbol",
    "description": "Look up the real, complete definition of a named Solidity symbol (contract, interface, struct, enum, function, or modifier) in the target project. Use this only when genuinely unsure of a symbol's real fields/signature/modifiers — the file map, callable_api, scaffold, and example already answer most cases.",
    "parameters": {
      "type": "object",
      "properties": {
        "name": {"type": "string", "description": "the exact symbol name to look up"}
      },
      "required": ["name"]
    }
  }
}
```

Passed via Ollama's `/api/chat` `tools` array. Exactly one tool is declared
(FR-outof-scope: no second tool in this feature).

## Request (model → harness)

The model, when unsure of a symbol's real definition, emits a tool call — returned
by Ollama as `message.tool_calls: [{"function": {"name": "lookup_symbol",
"arguments": {"name": "<symbol name>"}}}]`. Multiple tool calls MAY appear in one
`message.tool_calls` list; each is resolved and counted against the Lookup Budget
independently, in order, up to the remaining budget (same rule as spec 007).

**Rules for the model** (stated in the tool's `description`, not prose in the main
prompt — this is the point of the structured schema): only call `lookup_symbol`
when genuinely unsure; the static grounding blocks already answer most cases.

## Response (harness → model)

For each tool call resolved (up to the remaining Lookup Budget), the harness
appends:
1. The assistant's message as returned (including its `tool_calls`), unmodified.
2. One message per resolved call:
   ```json
   {"role": "tool", "content": "<rendered result — see below>"}
   ```

The rendered result content is semantically IDENTICAL to spec 007's `[DATA] <name>
resolved to N definition(s): ...` / `NOT FOUND` text
(`_render_lookup_response()`-equivalent), including the nested-type-import NOTE for
struct/enum matches — SC-002 requires this be verified byte-identical between
protocols in the offline test suite, not just "equivalent in spirit."

The harness then re-issues the `/api/chat` request with the extended message list
and the SAME `tools` declaration, so the model may call `lookup_symbol` again
(within budget) or produce its final answer.

## Budget exhaustion

Once the Lookup Budget for the current attempt is exhausted, the harness does NOT
perform another tool-calling round-trip: whatever content the model's next message
contains is treated as final, with any residual `tool_calls`/scaffolding stripped
(FR-007) before being treated as PoC source.

## Logging

Every tool call (resolved or not) is logged in the SAME shape as spec 007's
text-marker protocol:

```json
{"event": "lookup", "finding_id": "...", "attempt": N, "symbol": "<name>",
 "resolved": true|false, "match_count": M}
```

No new field distinguishes which protocol produced a given log entry — FR-006
requires this be indistinguishable to a downstream log consumer (Protocol Mode is
recorded separately, once per run, not per lookup event, if recorded at all).

## Interaction with existing static grounding

Additive, exactly as spec 007 (research.md R6 there): the file map, callable_api,
scaffold, and few-shot example remain part of the initial user-turn content;
`lookup_symbol` is an escape hatch, not a replacement for static grounding.

## Final-output extraction (FR-007)

The harness accepts the model's final message content ONLY once it contains no
further tool call — i.e., `message.tool_calls` is empty/absent on that turn. The
accepted content is then run through the same fence-stripping (`_strip_fences()`)
already applied to the text-marker path, so a model that wraps its final Solidity
source in markdown fences (despite using structured tool calls for lookups) is
still handled identically to the existing protocol.
