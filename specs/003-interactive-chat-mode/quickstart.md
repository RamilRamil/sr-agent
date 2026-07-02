# Quickstart: Interactive Chat Mode

## Prerequisites

Same environment as any other `sr-agent` command:

```bash
cd /Users/ramilmustafin/Claude/Projects/SR-agent
export ANTHROPIC_API_KEY=dummy   # unused by chat mode itself — required only because
                                  # config.load_config() still hard-requires it today
export SR_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
```

Ollama running with a pulled model (`qwen2.5-coder:3b` or `sr-stage2` once fine-tuned) — chat mode refuses turns outright when this isn't available (FR-011), it does not degrade to relay-only automatically.

## Starting a session

```bash
PYTHONPATH=. .venv/bin/python -m sr_agent.cli chat /path/to/target/contracts --project-id strata-bb
```

Prints the new `session_id` and drops into a REPL.

## Example turn — Q&A (User Story 1)

```
> what's the coverage-manipulation exploit path again?
```

Routes local-first. `SessionFacts.known_finding_ids` already contains the finding if it was recorded via a prior `audit` run against the same `project_id` — the agent answers from that, not from re-deriving it. No tool call needed for a pure recall question; `tool_invocations` on this turn is empty.

## Example turn — PoC request (User Story 2, R8)

```
> write a PoC for the metaKey sentinel-collision finding
```

The turn's `AgentAction.next_action` resolves to `write_poc`. Because that's in `REQUIRES_OOB_CONFIRMATION`, the session does **not** write the file inline. It prints:

```
Requesting confirmation to write_poc for finding F3-metakey-sentinel-collision
  confirmation id: 3f9a1c2e-...
Run: sr-agent confirm 3f9a1c2e-... --approve
Session paused. Resume with: sr-agent chat --resume <session_id>
```

and exits `0`. In a separate terminal:

```bash
PYTHONPATH=. .venv/bin/python -m sr_agent.cli confirm 3f9a1c2e-... --approve
```

Then resume:

```bash
PYTHONPATH=. .venv/bin/python -m sr_agent.cli chat --resume <session_id>
```

The turn completes: `write_poc` runs, `run_tests` runs inside `DockerSandbox`, and the chat prints the pass/fail outcome in the same conversation (SC-002) — this is exactly the "small model writes PoC" workflow, but with the out-of-band gate `scripts/poc_queue_runner.py` deliberately skipped for expediency now properly in place.

## Example turn — irreversible action blocked (User Story 3)

Any request whose action resolves to a `write_execute` type always goes through the flow above — there is no request phrasing that skips it (SC-003: 100% of matching requests blocked from direct execution).

## Example turn — local model down (FR-011)

```
> show me SharesCooldown.sol
Local model unavailable — turn not processed. Resume once Ollama is reachable:
  sr-agent chat --resume <session_id>
```

No relay fallback happens automatically, even though this particular question could have been answered by relay too — FR-011 is unconditional on this point.

## Verifying session resumability (FR-012)

```bash
# Terminal 1
sr-agent chat /path/to/target --project-id strata-bb
> what's finding F1 about?
<answer>
^D

# Terminal 2, later
sr-agent chat --resume <session_id>
> and what was F2 again?
<answer, still grounded in the same SessionFacts>
```

## Running the test suite for this feature

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/unit/test_chat_session.py tests/unit/test_chat_reasoning.py tests/unit/test_orchestrator_loop_chat.py tests/integration/test_chat_cli.py tests/security/test_chat_mi_scenarios.py -v
```
