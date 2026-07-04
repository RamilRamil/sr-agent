# Contract: Live-Trace WebSocket

The "what the agent is thinking now" stream (US1/FR-004–FR-006, SC-002).

## Endpoint

`WS /ws/session/{session_id}` — the operator's browser opens one socket per active session. The backend runs the turn (`loop.run_turn`) with an `event_sink` that pushes `TraceEvent`s onto an in-process bus fanned to this socket.

## Message shape

Server → client only (the browser sends nothing but the initial subscribe). One JSON `TraceEvent` per message (data-model.md): `{ "type": ..., "source_type": ..., ...payload }`.

Event order for a typical turn:
```
turn_start → (reasoning → routing → [token…] → tool → budget)* → outcome
```
- `reasoning`/`routing`/`budget`/`tool` mirror each ReAct step.
- `token` (optional) forwards generated tokens so a slow local turn is visibly alive (FR-006) — the local client already streams NDJSON internally, so this is cheap.
- `escalation` appears when a deterministic trigger fires (which one + why).
- `outcome` is terminal for the turn (completed / paused_confirmation / paused_relay / blocked_local_unavailable / budget_exhausted). On `paused_confirmation`, the browser refetches `/api/confirmations`.

## Guarantees

- **Observability only** — the stream is produced by the kernel `event_sink` hook; it cannot influence control flow or any invariant (Constitution I). If no socket is connected, the loop runs identically (sink is `None`-safe).
- **Reconnect** — reopening the socket re-attaches to the running session and resumes streaming current state (spec edge case: reconnect mid-turn does not lose it).
- **Liveness on a down model** — if the local model is not ready, the turn yields a `blocked_local_unavailable` `outcome` and the UI shows blocked; no fabricated progress, no silent relay fallback (FR-011).
- **Trust tags** — every `token`/`tool` event from the model is `external_llm_output`; the UI renders it inert and never promotes it.
