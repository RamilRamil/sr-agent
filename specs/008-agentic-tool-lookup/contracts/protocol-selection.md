# Contract: Lookup Protocol Selection

How the harness decides, once per run, whether a draft/fix attempt uses spec
007's `LOOKUP:` text-marker protocol or this feature's native tool-calling
protocol.

## Inputs

- `--lookup-protocol {auto,tool,marker}` CLI flag (default `auto`).
- `LocalClient.supports_tools()` — capability detection (research.md R2): the
  configured model's entry in `GET /api/tags`' response includes `"tools"` in its
  `capabilities` list.

## Decision table

| `--lookup-protocol` | `supports_tools()` | Resulting Protocol Mode |
|---|---|---|
| `auto` (default) | `true` | `tool` (`source: detected`) |
| `auto` (default) | `false` | `marker` (`source: detected`) |
| `tool` | `true` | `tool` (`source: forced`) |
| `tool` | `false` | **error at startup** — the operator explicitly asked for tool-calling on a model that doesn't support it; the harness MUST fail clearly rather than silently substitute the marker protocol (an explicit forced choice deserves an explicit failure, not a silent downgrade) |
| `marker` | (either) | `marker` (`source: forced`) — always available, since it's spec 007's existing text-based protocol, model-agnostic by construction |

## Timing

Selection happens ONCE, at the same point in `main()` where `client.warm()`/
`client.ready()` already run (before extraction, before any draft/fix attempt) —
never re-evaluated mid-run, never re-evaluated per-attempt (research.md R4: no
mid-run downgrade).

## Logging

The selected Protocol Mode is logged once, alongside the existing
`{"event": "scaffold_mode", ...}` entry (or as its own event), e.g.:

```json
{"event": "lookup_protocol", "mode": "tool", "source": "detected"}
```

so a run's log is self-describing about which protocol produced its `lookup`
events, without requiring a per-event field (FR-006 keeps the per-event shape
identical across protocols).

## Interaction with `--no-symbol-index` / `--lookup-budget 0`

Unchanged from spec 007: if `--no-symbol-index` is set, or `--lookup-budget 0`,
no lookup round-trip of EITHER kind is attempted — Protocol Mode selection is
irrelevant in that case (both protocols are simply unused).
