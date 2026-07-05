# Feature Specification: Native Agentic Tool-Calling for PoC Symbol Lookup

**Feature Branch**: `008-agentic-tool-lookup`

**Created**: 2026-07-05

**Status**: Draft

**Input**: User description: "Native agentic tool-calling for PoC symbol lookup (SR-agent PoC-workability harness). Motivation: spec 007 shipped a bounded lookup mechanism (SymbolIndex + a `LOOKUP: <name>` protocol) that measurably helped a live H-01 run get past two full compile-error classes it was previously stuck on. But the mechanism itself is architecturally a TEXT-MARKER CONVENTION layered on top of ordinary freeform generation... Ollama's native tool-calling API (`/api/chat` with a `tools` array of JSON-schema function definitions, returning `message.tool_calls`) is genuinely available for the model actually in use (`qwen3-coder:30b` reports `capabilities: [completion, tools]`). Scope: (1) add a real Ollama-native tool-calling round-trip declaring a single tool `lookup_symbol(name)`, replacing the text-marker detection for tool-capable models; (2) preserve every existing observability/bookkeeping contract from spec 007 unchanged (budget, log shape, resolution semantics); (3) graceful degradation to spec 007's existing `LOOKUP:` protocol for non-tool-capable models/hosts; (4) validate offline first and primarily; live validation against H-01 is optional/lower-priority given three Kaggle GPU sessions were already spent validating spec 007's mechanism. Out of scope: additional tools beyond `lookup_symbol`; changing SymbolIndex resolution semantics; wiring into the kernel's orchestrator; switching providers/models; guaranteeing H-01 convergence."

## User Scenarios & Testing *(mandatory)*

The "user" is the SR-agent **operator/maintainer** running the PoC-workability
harness — this is an internal capability/reliability feature for existing tooling,
not an end-user-facing product feature.

### User Story 1 - The lookup request is a structured object, not a hoped-for text pattern (Priority: P1)

As the operator, when the model needs a symbol's real definition mid-draft, I need
the request to be a genuine tool call the inference API itself parses and returns
as a typed object — not a `LOOKUP: Name` line the harness must regex-detect inside
otherwise-freeform generated text, which only works if the model happens to
reproduce the exact convention it was told about in prose.

**Why this priority**: This is the entire motivating gap — spec 007's mechanism
works, but its reliability depends on a text convention rather than something the
inference layer structurally guarantees. Closing that gap is the point of this
feature.

**Independent Test**: Feed the harness a scripted/fake Ollama tool-calling response
containing a `lookup_symbol` tool call and confirm the harness detects and resolves
it via the existing `SymbolIndex`, without any text-pattern regex involved in the
detection path.

**Acceptance Scenarios**:

1. **Given** a tool-capable model/host, **When** the model issues a `lookup_symbol`
   tool call during a draft/fix attempt, **Then** the harness resolves it via
   `SymbolIndex.lookup()` and returns the result as a structured tool result, not by
   scanning the model's text output for a marker string.
2. **Given** the model issues more than one tool call in a single turn, **Then** each
   is resolved and accounted against the same per-attempt lookup budget spec 007
   already enforces.

---

### User Story 2 - Every existing observability and resolution contract survives unchanged (Priority: P1)

As the operator, I need the switch to native tool-calling to change ONLY how a
lookup request round-trips — not what gets resolved, how ambiguity is handled, how
qualified/nested-type names are normalized, or how lookups are logged — so that
spec 007's already-validated correctness (qualified-name fallback, nested-type
import guidance, never-fabricate-on-miss) isn't put at risk by this change.

**Why this priority**: This feature is a control-flow/protocol change, explicitly
NOT a resolution-logic change (per the feature's own scope). Any drift here would
silently reopen bugs spec 007 already closed.

**Independent Test**: Run the exact same offline symbol-resolution test cases spec
007 already has (qualified-name fallback, nested-type struct/enum, ambiguous
multi-match, not-found) through the NEW tool-calling round-trip and confirm
byte-identical resolution results and an identical `{"event": "lookup", ...}` log
shape to the existing text-marker path.

**Acceptance Scenarios**:

1. **Given** a symbol lookup that would resolve a certain way under spec 007's
   `LOOKUP:` protocol, **When** the same lookup is made via a native tool call,
   **Then** it resolves identically (same matches, same qualified/nested-type
   handling).
2. **Given** any lookup made through either protocol, **Then** it produces the same
   `{"event": "lookup", "finding_id", "attempt", "symbol", "resolved",
   "match_count"}` log entry shape, so downstream log analysis doesn't need to know
   which protocol produced it.

---

### User Story 3 - A model/host without tool-calling support keeps working exactly as before (Priority: P2)

As the operator, I need the harness to keep working unmodified against any model or
`--host` that doesn't support native tool-calling (an older/smaller model, or a
host whose Ollama version predates the feature) — falling back automatically to
spec 007's existing `LOOKUP:` text-marker protocol — so this feature never becomes
a hard requirement for using the harness at all.

**Why this priority**: The harness must remain usable with whatever model the
operator has actually pulled; not every model reports `"tools"` in its Ollama
capabilities.

**Independent Test**: Point the harness at a scripted/fake host reporting no
`"tools"` capability and confirm the run proceeds using spec 007's existing
text-marker protocol, with no crash, no operator-visible difference in outcome
quality, and no manual flag required.

**Acceptance Scenarios**:

1. **Given** a configured model/host that does not report tool-calling support,
   **When** a draft/fix attempt needs a lookup, **Then** the harness automatically
   uses the existing `LOOKUP:` text-marker protocol without operator intervention.
2. **Given** a tool-capable model/host, **When** the operator explicitly wants the
   old protocol (e.g. for comparison), **Then** an explicit override is available.

---

### User Story 4 - Optional evidence from a real finding (Priority: P3)

As the operator, I would like to know whether native tool-calling changes anything
observable on a real finding compared to spec 007's already-recorded baseline — but
this is explicitly optional and lower priority, since spec 007 already spent three
live Kaggle sessions validating the underlying lookup mechanism itself, and this
feature only changes the request/response transport, not what gets resolved.

**Why this priority**: Lowest priority — offline validation (User Stories 1-3)
already proves the mechanism is correct; a live comparison is a nice-to-have, not
a requirement, and must not be used to justify additional live-testing budget
beyond what the operator explicitly authorizes.

**Independent Test**: If run, compare a live attempt using native tool-calling
against spec 007's already-documented H-01 baseline in `docs/roadmap.md`, recording
the comparison honestly (including "no observable difference," which is a valid
outcome given this feature changes transport, not resolution logic).

**Acceptance Scenarios**:

1. **Given** spec 007's recorded H-01 baseline, **When** a live run is optionally
   executed with native tool-calling enabled, **Then** the outcome is recorded and
   honestly compared — without claiming new convergence as evidence this feature
   works (offline tests are the actual completion bar).

### Edge Cases

- What happens when the model issues a tool call with a malformed or missing `name`
  argument? → The harness must treat it as an unresolved lookup (log it, count it
  against budget) rather than crash.
- What happens when the model issues more tool calls in one turn than the remaining
  budget allows? → Only the remaining budget's worth are resolved; the rest are
  treated the same way spec 007 already treats budget exhaustion (force the model
  to proceed with what it has).
- What happens when a host reports `"tools"` capability but a specific tool-calling
  request still fails at generation time (an unreliable real-world implementation)?
  → That attempt fails the same way any other generation failure already does in
  the harness's existing retry/repair loop — this feature does not add a new
  mid-run downgrade mechanism from tool-calling to text-marker.
- What happens when the final accepted PoC source still contains tool-call
  scaffolding (e.g. a stray tool-call JSON fragment) after the round-trip
  completes? → The harness must strip it before writing the PoC file, same as it
  already strips markdown fences from text-based output.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The harness MUST support a native Ollama tool-calling round-trip
  (`/api/chat` with a `tools` schema, detecting `message.tool_calls`) for a single
  tool, `lookup_symbol(name: string)`, during PoC draft/fix attempts.
- **FR-002**: Every tool call MUST be resolved via the existing
  `SymbolIndex.lookup()` — this feature MUST NOT change resolution semantics,
  ambiguity handling, qualified-name fallback, or nested-type guidance already
  shipped in spec 007.
- **FR-003**: The harness MUST detect whether the configured model/host supports
  tool-calling (via Ollama's reported capabilities) and select the appropriate
  protocol automatically, without requiring an operator to know or specify which
  protocol a given model needs.
- **FR-004**: For a model/host without tool-calling support, the harness MUST fall
  back to spec 007's existing `LOOKUP:` text-marker protocol with no regression in
  behavior or outcome quality.
- **FR-005**: The per-attempt lookup budget (`--lookup-budget`) MUST be enforced
  identically regardless of which protocol is in use.
- **FR-006**: Every lookup, made via either protocol, MUST be logged in the same
  `{"event": "lookup", "finding_id", "attempt", "symbol", "resolved",
  "match_count"}` shape already established by spec 007.
- **FR-007**: The final PoC source accepted from a tool-calling round-trip MUST be
  free of any tool-call scaffolding (no partial tool-call JSON, no leftover
  role/tool artifacts) — clean Solidity source only, same bar as the existing
  markdown-fence stripping for text-based output.
- **FR-008**: An operator MUST be able to explicitly force either protocol (native
  tool-calling or the text-marker fallback) via a CLI flag, for comparison or
  debugging, overriding the automatic capability-based selection.
- **FR-009**: Live validation against a real finding (e.g. H-01) is OPTIONAL for
  this feature; if performed, its outcome MUST be honestly compared against spec
  007's already-recorded baseline in `docs/roadmap.md` rather than presented as a
  new, independent success claim.

### Key Entities

- **Tool Call**: a model-issued, structured request (name + arguments) to invoke
  `lookup_symbol`, returned by the inference API as a typed object rather than
  extracted from free text.
- **Tool Result**: the harness's structured response to a Tool Call, resolved via
  the existing `SymbolIndex` and appended to the conversation for the model to
  continue from.
- **Protocol Mode**: which lookup protocol (native tool-calling vs. spec 007's
  text-marker fallback) was used for a given attempt — recorded for
  observability/comparison, not exposed as an operator-facing concept beyond the
  override flag.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a tool-capable model, 100% of lookup requests in the offline test
  suite arrive as structured tool-call objects, with zero reliance on text-pattern
  matching in the detection path.
- **SC-002**: The exact same set of resolution test cases (qualified-name fallback,
  nested-type struct/enum, ambiguous multi-match, not-found) produce byte-identical
  results whether resolved via native tool-calling or the text-marker fallback,
  verified entirely offline (no live model needed).
- **SC-003**: A model/host without tool-calling support completes a full draft/fix
  run with zero operator-visible errors attributable to this feature, automatically
  using the fallback protocol.
- **SC-004**: 100% of lookups, regardless of protocol, appear in the run log in the
  pre-existing shape — no downstream log consumer needs to change.
- **SC-005** (secondary, only if live-validated): Any live comparison against spec
  007's H-01 baseline is recorded with an explicit, honest verdict — including "no
  observable difference," which is a valid and acceptable outcome.

## Assumptions

- The "operator" is the person running `scripts/poc_queue_runner.py` — this is an
  internal capability feature for existing tooling, not an end-user product
  feature.
- Ollama's tool-calling API (`/api/chat`, `tools` parameter, `message.tool_calls`)
  is the target mechanism, since the harness is Ollama-hosted throughout (per
  existing project convention: no paid API dependency). A future switch to a
  different inference backend is out of scope.
- Capability detection at model/host warm-up (mirroring the existing
  `available()`/`ready()` pattern in `sr_agent/llm_core/local_client.py`) is
  sufficient; this feature does NOT add a mid-run downgrade mechanism if a
  tool-capable host's tool-calling request unexpectedly fails at generation time —
  that failure is handled by the harness's existing generation-failure/retry path,
  same as any other generation error.
- Reimplementing spec 007's `SymbolIndex`/resolution logic is explicitly out of
  scope — this feature only changes how a lookup request/response round-trips
  between harness and model, never what a lookup returns.
- No new dependency is required beyond what spec 007 already introduced
  (`solidity-parser`) — Ollama's tool-calling API is reached via the same stdlib
  `urllib`-based HTTP calls `LocalClient` already uses, per the project's
  no-paid-API, minimal-dependency convention.
- Live validation against H-01 (or any real finding) is optional and, if pursued,
  must not be treated as the feature's completion bar — the offline test suite
  (User Stories 1-3 / SC-001-004) is.
