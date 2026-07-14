# Research: OpenRouter / GLM Provider (spec 020)

Verified hands-on this session against `https://openrouter.ai/api/v1/models`.

## Decision 1: `z-ai/glm-5.2` is the GLM slug (verified)

**Decision**: Default the OpenRouter model dropdown to `z-ai/glm-5.2`.

**Rationale**: Fetching OpenRouter's live `/models` returned exactly one GLM entry — id `z-ai/glm-5.2`, name "Z.ai: GLM 5.2" (1M-token context, positioned for "long-horizon agent workflows, project-level software engineering"). No `glm-5`/`glm-4.6` variants were listed. So the operator's "GLM 5.2" is real and current.

**Alternatives considered**: hardcoding a guessed slug (rejected — verified the real one); a live `/models` fetch to populate the dropdown (deferred — needs network/key, non-deterministic; a curated static list is offline-testable and refreshable).

## Decision 2: stdlib HTTP client, no new package (FR-007)

**Decision**: `OpenRouterClient` POSTs to `https://openrouter.ai/api/v1/chat/completions` with `urllib.request` (stdlib), mirroring `LocalClient`. No `openai` SDK, no `requests`-as-new-dep (requests is already a base dep but urllib keeps it self-contained and matches LocalClient's style).

**Exact call (OpenAI-compatible)**:
```
POST https://openrouter.ai/api/v1/chat/completions
Headers: Authorization: Bearer <key>, Content-Type: application/json
Body:    {"model": "<slug>", "messages": [{"role": "user", "content": prompt}],
          "response_format": {"type": "json_object"}   # only when fmt == "json"}
Read:    resp["choices"][0]["message"]["content"]
```
Optional OpenRouter ranking headers (`HTTP-Referer`, `X-Title`) are omitted — not required for the call.

**Rationale**: FR-007 forbids a new package; Principle V wants the paid path isolated and dependency-free. urllib is already how `LocalClient` talks to Ollama, so the style and error handling are consistent.

**Alternatives considered**: `openai` SDK pointed at OpenRouter's base_url (rejected — new package, violates FR-007); the `anthropic`/`google-genai` clients (wrong protocol).

## Decision 3: Reuse the spec-018/019 slot machinery + duck interface

**Decision**: `OpenRouterClient` implements `generate(prompt, fmt=None, options=None) -> str` and `ready() -> bool` only — the methods `ChatReasoningProvider` calls. Add a `backend == "openrouter"` branch to `reasoning_client()` (main) and `additional_client()` (additional). Extend the allowed backend sets: MAIN `{"local","paid","openrouter"}`, ADDITIONAL `{"local","paid","openrouter","off"}`.

**Rationale**: Drop-in with the existing slots; no provider/session change. Verified the existing `test_backend_must_be_local_or_paid` posts `{"backend":"nonsense"}` → 400, so adding "openrouter" to the allowed set does NOT break it.

## Decision 4: Key = env-first, write-only UI override

**Decision**: `config.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")`. `effective_openrouter_key()` on a slot = `_paid_key or config.openrouter_api_key` (the existing per-slot write-only key overrides env, like spec 018's Gemini key). No key → `additional_client()` returns `None` and a main OpenRouter client's `ready()` is False (clear disabled state).

**Rationale**: The operator chose env as the documented path; the write-only UI key stays available for parity, reusing the exact spec-018 mechanism (`_paid_key`, `public()` exposes only `has_paid_key`). One slot key field, env fallback keyed by the slot's method.

**Note**: `_paid_key` is a single per-slot secret shared by the hosted methods; the env fallback it resolves against depends on the method (`gemini_api_key` for "paid", `openrouter_api_key` for "openrouter"). This is unambiguous because a slot has exactly one method at a time.

## Decision 5: `ready()` makes no network/paid call

**Decision**: `ready()` returns `bool(self.api_key)` — key present ⇒ ready. No probe request.

**Rationale**: A probe would cost money and break offline use; a bad key surfaces on the first real `generate()` (spec edge case). Same posture as `GeminiClient.ready()`.

## Trust status — no new code

OpenRouter output rides `ChatTurn` (default `external_llm_output`, forbids human/inference tiers), so it is untrusted by construction (FR-006). A test asserts it; no production trust code is added.
