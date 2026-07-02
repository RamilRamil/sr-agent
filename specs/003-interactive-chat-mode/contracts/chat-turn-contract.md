# Contract: one chat turn (`ChatReasoningProvider` ↔ `OrchestratorLoop`)

This is the internal contract R2 introduces — the interface `OrchestratorLoop` needs from whatever plays the role `ClaudeClient` used to play. Written as a contract (not just a class signature) because it's the seam where FR-011 (refuse-and-wait) and R3 (escalation routing) are actually enforced, so it needs to be testable independent of the CLI.

## Interface

```python
class ChatReasoningProvider(Protocol):
    def complete(self, messages: list[dict]) -> ReasoningOutcome: ...
```

This is a slightly wider return type than `ClaudeClient.complete`'s bare `AgentAction`, because a chat turn has three possible outcomes `ClaudeClient` never needed to express (it always either returns an `AgentAction` or raises `ValueError` on unparseable output):

```python
@dataclass
class ReasoningOutcome:
    kind: Literal["action", "blocked_local_unavailable", "paused_relay"]
    agent_action: AgentAction | None      # set iff kind == "action"
    relay_request_id: str | None          # set iff kind == "paused_relay"
```

## Preconditions

- `messages` is already DATA-wrapped for every non-system-prompt entry (caller's responsibility, via `context.build_messages`/`wrap_data` — unchanged from today).
- The `SessionFacts` bucket (R6) is already folded into `messages` by the caller before `complete()` is invoked — `ChatReasoningProvider` does not know about `ChatSession`/`SessionFacts` at all, keeping it a pure "messages in, outcome out" function, same shape as `ClaudeClient.complete`.

## Behavior contract

1. **Local-first, always.** Call `LocalClient.available()`. If `True`, generate with the local model, parse strictly as `AgentAction` (same discipline as `ClaudeClient._parse_response` — malformed JSON does not fall through to relay, it's a parse failure the caller retries or reports, same as `loop.py`'s existing `except ValueError: continue` handling).
2. **If local is unavailable**: return `ReasoningOutcome(kind="blocked_local_unavailable", ...)` immediately. **Never** attempt relay as a substitute for an unavailable local model — this is the one behavior FR-011 explicitly forbids conflating with escalation.
3. **After a successful local `AgentAction`, check escalation** — in this order:
   - a. `guardrails/escalation.py::evaluate_triggers()` against the action/finding/session (R3). Deterministic, cannot be suppressed by the model's own text.
   - b. The model's own `agent_action.escalation_trigger` field, if (a) didn't already fire.
   - If either fired: do **not** return the local `AgentAction` as the turn's outcome. Instead, file a relay request (reusing `orchestrator/relay.py::request_analysis`-equivalent, single-turn payload instead of a findings-list payload) and return `ReasoningOutcome(kind="paused_relay", relay_request_id=...)`.
   - If neither fired: return `ReasoningOutcome(kind="action", agent_action=...)` — this is the common, fast, local-only path.
4. **Never silently retry a different tier.** Every outcome is one of exactly three kinds; there is no fourth "tried both, here's whichever worked" behavior. This is deliberate — FR-010 requires being able to tell which tier produced any given result, which is only guaranteed if the routing is a single deterministic decision per attempt, not a race or silent retry cascade.

## Postconditions the caller (`OrchestratorLoop`) relies on

- `kind == "action"` → `agent_action.next_action` is a valid `ActionType` value (parse already enforced this) and the loop proceeds exactly as it does today: persist finding if present, check terminal actions, `validate_action`, gate-if-required, dispatch.
- `kind == "blocked_local_unavailable"` → the loop sets `ChatSession.status = "blocked_local_unavailable"` and returns control to the CLI layer (no further iteration this turn) — see `cli-chat-command.md`.
- `kind == "paused_relay"` → the loop sets `ChatSession.status = "paused_relay"`, `pending_relay_request_id = relay_request_id`, and returns control the same way.

## Testability

Because `ChatReasoningProvider` is injected (R2), tests exercise `OrchestratorLoop` against a fake implementing this exact contract — no Docker, no real Ollama, no real relay files needed to test the loop's dispatch/confirmation/budget logic. Separately, `ChatReasoningProvider`'s own local-first/escalation-routing logic is tested against a fake `LocalClient` and a fake `evaluate_triggers`, independent of the loop. This mirrors how `tests/unit/test_action_validation.py` already tests `validate_action` in isolation from anything that calls it.
