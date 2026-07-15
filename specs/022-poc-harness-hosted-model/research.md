# Research: Report→PoC Batch on a Hosted Model (spec 022)

All findings verified this session by reading `scripts/poc_queue_runner.py` and the client modules.

## Decision 1: Swap the client only on the marker path — a `generate`-duck seam

**Decision**: Drive the batch with any `generate(prompt, fmt=None, options=None) -> str` client on the `marker` lookup protocol.

**Rationale**: `_select_protocol` returns immediately for `"marker"` WITHOUT calling `client.supports_tools()`, and the tool-calling `client.chat()` path is only taken under the `tool` protocol. On the marker path the harness's model calls are exclusively `client.generate(...)` (extract_tasks, the marker round-trip, draft/fix). `LocalClient.generate`, `OpenRouterClient.generate`, `GeminiClient.generate` share the same signature; hosted clients ignore `options` and honor `fmt="json"`. So no adapter class is needed — just build the right client and force marker.

**Alternatives considered**: a `ReasoningClient` Protocol / adapter (rejected — YAGNI; the three concrete clients already share the two methods used). Making hosted clients implement `chat`/`supports_tools`/`warm` (rejected — unnecessary for marker).

## Decision 2: Provider factory + hosted-aware startup gate

**Decision**: `build_generation_client(provider, model, host, timeout)`:
- `local` → `LocalClient(model=model or MODEL, host=host, timeout_s=…)` (today's build).
- `openrouter` → `OpenRouterClient(api_key=os.environ["OPENROUTER_API_KEY" or ""], model=model or "z-ai/glm-5.2")`.
- `gemini` → `GeminiClient(api_key=os.environ["GEMINI_API_KEY" or ""], model=model or SIMPLE_MODELS[0])`.

The startup block in `main()` currently: builds LocalClient, starts a keep-alive thread pinging `client.available()`, then `client.warm()` + `client.ready()`. For hosted, SKIP the keep-alive thread and `warm()`/`available()` (Ollama-only), and gate on `hosted_ready_error(...)`:
- no effective key → abort "no <PROVIDER>_API_KEY configured".
- gemini with a key but `ready()` False → the SDK is missing → abort "install google-genai (pip install '.[gemini]')".
- else ready.

**Rationale**: `available()`/`warm()` don't exist on hosted clients; `ready()` (key present) is the right readiness signal. `GeminiClient.ready()` returns False for BOTH no-key and no-SDK, so distinguish by checking the effective key first (no-key message), then attribute a key-present-but-not-ready to a missing SDK (install message).

## Decision 3: Force the marker protocol for hosted, error on explicit `tool`

**Decision**: `resolve_lookup_protocol(provider, requested)`:
- `local` → `requested` unchanged (auto/tool/marker as today).
- hosted + `requested == "tool"` → raise a clear startup error (hosted models have no tool-calling here) — consistent with the existing "explicit tool on an unsupported model is a startup error, not a silent downgrade" policy.
- hosted + `auto`/`marker` → `"marker"`.

**Rationale**: hosted clients don't implement `chat`/`supports_tools`; the tool protocol can't run on them. Forcing marker (and erroring on an explicit tool request) matches the harness's existing no-silent-downgrade stance.

## Decision 4: Widen annotations, no new class

**Decision**: Change `client: LocalClient` on the marker/draft/fix functions to `LocalClient | OpenRouterClient | GeminiClient`. Import the two hosted clients at the top of the harness (both import-safe; Gemini's SDK is lazy).

**Rationale**: only `generate` is used on the marker path, so the union is accurate and requires no behavior change. `from __future__ import annotations` keeps annotations as strings (no runtime import cost), but importing the classes is harmless and keeps the union legible.

## Decision 5: Everything else unchanged; PASS still mechanical

**Decision**: Reuse whole-report extraction (no prefilter), grounding, scaffold, draft/fix, compile-gate, `_poc_defects`, mutation-verify, optional `--fork` verbatim. A compiling/PASS PoC remains a mechanical reproduction; the structural gate + vacuous-pass guard are the arbiters (memory `project_poc_vacuous_pass`).

**Rationale**: The feature's thesis is "same machinery, capable model." Changing the pipeline would confound whether a better result came from the model or a pipeline change.

## Testability boundary

Offline tests exercise the three pure helpers (factory, protocol resolution, readiness gate) + a mocked `generate` through the client, using monkeypatched env and fake clients — no real hosted call, no network, no Docker. The real end-to-end (live GLM + sandboxed forge over a real report) is a live operator run, out of the automated suite (recorded in the spec Assumptions).
