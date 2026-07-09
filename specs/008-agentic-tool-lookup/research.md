# Research: Native Agentic Tool-Calling for PoC Symbol Lookup

## R1 — Why revisit spec 007's own rejection of tool-calling

**Decision**: Proceed with native tool-calling now, as a planned fulfillment of a
condition spec 007 itself set, not a reversal made without new evidence.

**Rationale**: Spec 007's own research.md (R2) rejected a native tool-calling
schema in favor of the `LOOKUP:` text marker, explicitly because tool-calling
support was "unverified for these particular local builds," and closed with:
*"Revisit if the harness moves to models/backends with verified, reliable
tool-calling support."* This session has since verified exactly that: a direct
`GET /api/tags` against the Kaggle-hosted tunnel (running `qwen3-coder:30b`, the
model actually used for this session's live H-01 validation runs) reports
`"capabilities": ["completion", "tools"]`. The same is true locally for
`qwen2.5-coder:7b` and `qwen2.5-coder:3b` (checked against the project's own
`ollama` Docker container). The condition R2 set for revisiting has been met.

**Alternatives considered**: Leave the `LOOKUP:` protocol as-is — rejected because
the whole point of this feature (per the operator's explicit direction) is the
architectural upgrade from a hoped-for text convention to a structurally
guaranteed tool call, now that the prerequisite (verified tool support on the
in-use models) is satisfied.

## R2 — Capability detection: reuse the existing tag-matching pattern

**Decision**: Add `LocalClient.supports_tools() -> bool`, mirroring
`available()`'s existing pattern exactly: hit `/api/tags`, find the entry for
`self.model`, and check whether `"tools"` is in that entry's `capabilities` list.

**Rationale**: `available()` (`sr_agent/llm_core/local_client.py:45`) already
parses `/api/tags` and matches on `self.model` (exact-tag vs. any-tag rules for
untagged names). `supports_tools()` needs the identical model-matching logic, just
reading `capabilities` instead of only checking existence — reusing the matching
logic (as a shared helper) avoids a second, subtly-different implementation of
"which entry in `/api/tags` is my model."

**Alternatives considered**: Attempt a real tool-calling request and catch the
failure — rejected; this conflates "capability probing" with "spending a real
generation call," which is exactly the kind of avoidable cost this harness already
tries to bound (`ready()`'s own docstring already distinguishes a cheap liveness
check from a real generation probe for this reason).

## R3 — Request/response shape: Ollama's documented `/api/chat` `tools` contract

**Decision**: `POST /api/chat` with a `tools` array of `{"type": "function",
"function": {"name", "description", "parameters": <JSON Schema>}}` entries (one
entry: `lookup_symbol`); detect `message.tool_calls` (a list of `{"function":
{"name", "arguments"}}`) in the response; continue the conversation by appending
the assistant's message (including its `tool_calls`) followed by one `{"role":
"tool", "content": <json-stringified result>}` message per call, then re-issue the
chat request.

**Rationale**: This is Ollama's stable, documented tool-calling contract (in use
by Ollama's own function-calling examples and every downstream client library) —
the request/response SHAPE itself is not in question. Empirically re-verifying it
against a live model is NOT attempted locally: `docs/roadmap.md` gotcha #4 already
established that CPU-only local Ollama is not viable for interactive generation on
this hardware (a single call exceeded 30 minutes and was still incomplete) — this
applies to any `/api/chat` call, not only `/api/generate`, so a local probe is a
known dead end here, not worth retrying. What genuinely remains open — and is NOT
something a local CPU probe could answer even if it were viable — is whether the
ACTUAL Kaggle-hosted `qwen3-coder:30b` build reliably emits `tool_calls` as a real
structured object during live PoC drafting, instead of writing the call as plain
text despite the schema being declared. That question is deferred to optional
live validation (User Story 4 / FR-009, needing the Kaggle GPU tunnel this session
already used for spec 007's runs) rather than blocking this plan or being answered
by more local attempts.

**Alternatives considered**: OpenAI-compatible `/v1/chat/completions` (Ollama also
exposes this) — rejected; `/api/chat` is Ollama's native endpoint and is what
`LocalClient` already targets throughout (`/api/generate`, `/api/tags`), so
staying on the native endpoint avoids introducing a second API surface/dialect for
no benefit.

## R4 — No mid-run downgrade from tool-calling to text-marker

**Decision**: Capability detection happens once, at the same point `warm()`/
`ready()` already run (session start). If the detected-as-tool-capable host's
tool-calling request then fails at generation time, that single attempt fails the
same way any other generation failure already does in the harness's existing
retry/repair loop (already documented as an accepted design choice in spec.md's
Assumptions) — no new mid-run protocol-switching state machine.

**Rationale**: A mid-run downgrade mechanism (detect a tool-calling failure,
silently re-issue the same turn under the text-marker protocol, track which
protocol is "live" per attempt) is real, non-trivial state to build and test for
a failure mode that — if it happens at all — is already handled adequately by the
harness's existing attempt-level retry loop. Building it now would be exactly the
kind of premature complexity the project's own convention (YAGNI; no
speculative infrastructure before a second concrete need) argues against.

**Alternatives considered**: Per-attempt automatic fallback — rejected as
premature; revisit only if live validation (optional, User Story 4) actually
observes this failure mode in practice.

## R5 — Where the round-trip code lives

**Decision**: A thin transport addition to `sr_agent/llm_core/local_client.py`
(`supports_tools()`, and a `chat()` method parallel to the existing `generate()` —
same streaming-safety discipline against the cloudflared tunnel-idle-cutoff gotcha
#11/#12, same `ModelUnavailableError` contract) — the round-trip LOOP (budget
bookkeeping, `SymbolIndex` resolution, logging) stays in
`scripts/poc_queue_runner.py`, parallel to and reusing as much as possible of the
existing `_generate_with_lookups()`/`_render_lookup_response()` machinery from
spec 007.

**Rationale**: `LocalClient` already owns every Ollama HTTP transport concern
(`generate()`, `warm()`, `ready()`, `available()`) — a `chat()` method belongs
there for the same reason `generate()` does, not duplicated inside the harness
script. The ROUND-TRIP LOOP (deciding when to stop, how many lookups have been
used, what to log) is harness-specific policy that already lives in
`scripts/poc_queue_runner.py` for the text-marker protocol and should stay there
for symmetry and because it is intentionally outside the kernel's own
`OrchestratorLoop` (Constitution III/plan.md's Constitution Check).

**Alternatives considered**: Put the entire round-trip inside `LocalClient` —
rejected; `LocalClient` has no reason to know about `SymbolIndex`, lookup
budgets, or PoC-drafting concerns — that would blur a transport utility into
harness-specific policy.

## R6 — Operator override

**Decision**: `--lookup-protocol {auto,tool,marker}` CLI flag, default `auto`
(capability-detected). `tool` forces native tool-calling (erroring clearly if the
detected model doesn't support it, rather than silently falling back). `marker`
forces spec 007's existing text-marker protocol regardless of detected
capability — useful for direct A/B comparison (FR-008/SC-002).

**Rationale**: Matches the existing CLI convention (`--fork`, `--no-symbol-index`,
`--require-pass` are all explicit opt-in/override flags, not silent auto-behavior
changes) and directly serves SC-002's offline requirement to compare both
protocols' resolution behavior against the identical set of test cases.

**Alternatives considered**: Auto-only, no override — rejected; would make it
impossible to force a controlled offline comparison test (SC-002) or to debug a
suspected tool-calling issue by falling back deliberately.
