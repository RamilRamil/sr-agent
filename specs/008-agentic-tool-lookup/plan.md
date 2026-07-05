# Implementation Plan: Native Agentic Tool-Calling for PoC Symbol Lookup

**Branch**: `008-agentic-tool-lookup` | **Date**: 2026-07-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-agentic-tool-lookup/spec.md`

## Summary

Spec 007's `LOOKUP: <name>` protocol is a text-marker convention: the harness
prompts the model in prose to write a recognizable line, then regex-detects it in
otherwise-freeform output. This feature replaces that detection path — for models
that support it — with Ollama's native tool-calling API (`/api/chat`, a `tools`
JSON-schema array, `message.tool_calls` in the response), while leaving
`SymbolIndex` resolution semantics, the lookup budget, and the run-log shape
byte-identical to spec 007. Models/hosts without tool-calling support (detected via
Ollama's reported capabilities, mirroring `LocalClient.available()`'s existing
tag-matching pattern) automatically keep using spec 007's text-marker protocol —
this is a transport change, not a resolution-logic change.

## Technical Context

**Language/Version**: Python 3.11+ (matches the existing `scripts/`/`sr_agent` codebase)

**Primary Dependencies**: none new. Ollama's `/api/chat` endpoint is reached via the
same stdlib `urllib`-based HTTP pattern `sr_agent/llm_core/local_client.py` already
uses for `/api/generate` (`generate()`, `warm()`) — no HTTP client library, no
tool-calling SDK. `scripts/solidity_index.py`'s `solidity-parser` dependency
(spec 007) is untouched and unaffected.

**Storage**: N/A — no new persisted state; the existing `_runner_progress.jsonl`
run log gains no new fields (FR-006: identical log shape across both protocols).

**Testing**: pytest, entirely offline for the primary test suite (`tests/unit/
test_poc_queue_runner.py`, extended) — a scripted/fake Ollama chat response
(`message.tool_calls` payload) exercises the round-trip without a live model or
Docker, mirroring how spec 007's own round-trip logic was validated. Live
validation against a real finding (H-01 or otherwise) is optional per FR-009/User
Story 4 and is NOT part of this plan's completion bar.

**Target Platform**: unchanged — a local dev machine driving a Kaggle/Colab-hosted
Ollama instance over a `cloudflared` tunnel, same as the existing harness.

**Project Type**: single project — this extends an existing standalone script
(`scripts/poc_queue_runner.py`) and its test file; no new top-level directory, no
new service, no kernel involvement.

**Performance Goals**: none beyond what spec 007 already bounds (the per-attempt
lookup budget, `--lookup-budget`) — this feature does not change how many lookups
are permitted, only how a lookup request/response round-trips.

**Constraints**: no new dependency (Assumptions in spec.md); MUST NOT change
`SymbolIndex` resolution semantics (FR-002); MUST auto-detect tool-calling support
rather than requiring operator configuration (FR-003); MUST preserve the exact
`{"event": "lookup", ...}` log shape (FR-006).

**Scale/Scope**: one new tool schema (`lookup_symbol(name: string)`), a protocol-
selection function, a native tool-calling round-trip function parallel to the
existing `_generate_with_lookups()`, a CLI override flag, and offline test coverage
extending the existing `tests/unit/test_poc_queue_runner.py`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Secure-Kernel Trust Invariants** — PASS. This feature lives entirely inside
  `scripts/poc_queue_runner.py`, the standalone PoC-workability harness that
  already sits outside the kernel's `OrchestratorLoop`/tool-dispatch path (existing
  project convention, reaffirmed in spec 007's own Constitution Check and this
  spec's Assumptions). A tool CALL from the model is still resolved by fixed,
  deterministic Python (`SymbolIndex.lookup()`, unchanged) and the RESULT is still
  untrusted DATA appended to the prompt/conversation — no model output drives
  control flow. No change to `SourceType` trust hierarchy, memory signing, or
  tool-call budgeting in the actual kernel.
- **II. Human Authority for Privileged & Irreversible Actions** — PASS. No new
  privileged/irreversible action is introduced; `lookup_symbol` is a pure, local,
  read-only query against an already-parsed in-memory index. Nothing here touches
  `REQUIRES_HUMAN_CONFIRMATION` statuses or `write_execute`-class tools.
- **III. Kernel / Capability-Pack Separation** — PASS. No pack boundary is touched;
  this is entirely within the standalone harness, not a capability pack.
- **IV. Human-Gated Knowledge Promotion** — PASS. No knowledge-base writes; a
  `lookup_symbol` tool result is ephemeral, in-conversation DATA for one draft/fix
  attempt, never persisted as steering knowledge.
- **V. No Paid-API Dependency in the Core Path** — PASS. Still Ollama-only, reached
  via the same stdlib HTTP pattern already in use; no paid API introduced.

No violations — Complexity Tracking is empty.

**Post-design re-check (after Phase 0/1)**: research.md's decisions (transport
addition in `LocalClient`, round-trip loop staying in the standalone harness,
no mid-run protocol downgrade, single `lookup_symbol` tool) and data-model.md/
contracts/ don't introduce anything the initial Constitution Check didn't already
cover — still PASS on all five principles, no new violations surfaced by design.

## Project Structure

### Documentation (this feature)

```text
specs/008-agentic-tool-lookup/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
scripts/
├── poc_queue_runner.py   # EXTENDED: tool schema, protocol auto-detection
│                         #   (mirrors LocalClient.available()'s capability check),
│                         #   a native tool-calling round-trip parallel to the
│                         #   existing _generate_with_lookups(), a --lookup-protocol
│                         #   CLI override flag (FR-008)
└── solidity_index.py     # UNCHANGED (spec 007) — SymbolIndex resolution untouched

sr_agent/llm_core/
└── local_client.py       # POSSIBLY EXTENDED: a capability-detection helper
                          #   (e.g. supports_tools()) reusing the existing
                          #   /api/tags capabilities field, mirroring
                          #   available()'s tag-matching pattern; a chat() method
                          #   if /api/chat needs its own entry point distinct from
                          #   generate()'s /api/generate — exact shape decided in
                          #   research.md

tests/unit/
└── test_poc_queue_runner.py   # EXTENDED: tool-calling round-trip tests
                                #   (scripted/fake tool_calls payloads), protocol
                                #   auto-detection tests, fallback tests — no
                                #   model/Docker needed (mirrors existing style)
```

**Structure Decision**: Single project, extending the existing standalone harness
(`scripts/poc_queue_runner.py`) and its existing test file — no new top-level
directory. `sr_agent/llm_core/local_client.py` may gain a small, focused addition
(capability detection / a chat-endpoint method) if research concludes the
tool-calling round-trip is cleaner there than duplicated in the script; this stays
a kernel-adjacent LLM-transport utility, not kernel control-flow, consistent with
`local_client.py`'s existing role.

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*
