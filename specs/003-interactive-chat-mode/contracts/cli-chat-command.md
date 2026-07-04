# Contract: `sr-agent chat` CLI command

Follows the existing `cli.py` command conventions (`audit`, `resume`, `confirm`, `relay`) — `click`, same error-exit conventions (`sys.exit(2)` for usage errors), same `config.memory_root`/`config.confirmations_root`/`config.relay_root` wiring.

## Invocation

```
sr-agent chat <project-id-or-path> [--resume <session_id>] [--project-id <id>]
```

| Arg/Option | Required | Behavior |
|---|---|---|
| `<project-id-or-path>` | Yes (unless `--resume`) | Same resolution as `audit`'s positional arg: a path starting with a filesystem indicator is treated as the audit root; otherwise treated as an existing `project_id` to bind the session to. Opening a chat session for a project with no prior audit memory is allowed (spec Edge Case) — the session starts with empty `SessionFacts.known_finding_ids`, and the agent is expected to say so if asked about findings, not invent any. |
| `--resume <session_id>` | No | Loads an existing `ChatSession` via `EpisodicMemory.load(project_id, f"chat:{session_id}")` (R5). If the session's `status != "active"`, the resume path checks whether the pending item has since resolved (confirmation approved/rejected, relay response available, local model back up) and transitions accordingly before accepting new input — mirrors `resume_audit`'s ingest-then-continue shape. |
| `--project-id <id>` | No | Explicit override, same semantics as `audit --project-id`. |

## REPL behavior

- Each line of user input becomes one `ChatTurn`. The command loop is a plain read-eval-print — no streaming/partial-output contract implied.
- On a turn that resolves to `status: paused_confirmation` or `paused_relay`: the command prints the `ConsequentialActionNotice` (for confirmation) or the relay request id (for escalation), then **exits** (does not block polling) — the user re-invokes `sr-agent chat --resume <session_id>` after resolving the pending item out-of-band. This is R8's resolution: no in-process blocking wait.
- On a turn that resolves to `blocked_local_unavailable`: the command prints a clear "local model unavailable, turn not processed" message and exits — no relay fallback (FR-011). Re-invoking `--resume` retries once the local model is reachable.
- `Ctrl-C` / EOF ends the REPL process without altering `ChatSession.status` — an `active` session simply has no in-flight turn; resuming later continues normally.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Session ended normally (user quit) or a turn completed and the REPL is continuing (not an exit in this case — 0 only applies at process end). |
| `2` | Usage error (bad project id/path, `--resume` id not found) — matches existing `audit`/`resume` conventions. |
| `0` on pause | Pausing for confirmation/relay/local-unavailable is not an error — the command prints the pending-item info and exits `0`, consistent with `audit`'s existing "Stage 1 done, N target(s) need analysis via relay" pause message and exit code. |

## What this command does NOT do

- Does not accept a `--tool` or any flag that bypasses `validate_action`/confirmation for a specific turn — there is no "trust me" escape hatch in the CLI contract, matching FR-005's "MUST NOT execute... before that confirmation is granted" with no carve-out.
- Does not expose a machine-readable (JSON) output mode in this iteration — `audit`/`resume` don't either; out of scope here for the same reason.
