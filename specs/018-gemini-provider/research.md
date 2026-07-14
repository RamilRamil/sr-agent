# Research: Optional Gemini Model Provider (spec 018)

## Decision 1: SDK = `google-genai` (the current unified SDK)

**Decision**: Use `google-genai` (import `from google import genai`), not the legacy `google-generativeai`.

**Exact usage (verified against current PyPI, v2.11.x, Jul 2026):**
```python
from google import genai
from google.genai import types

client = genai.Client(api_key=key)                     # explicit key, not env-based
resp = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config=types.GenerateContentConfig(response_mime_type="application/json"),  # JSON mode
)
text = resp.text                                        # the generated string
for m in client.models.list():                          # programmatic model list
    ...
```

**Rationale**: `google-generativeai` is the older, superseded library; `google-genai` is Google's current, maintained unified SDK with a stable `Client(api_key=...)` constructor and a clean `.text` accessor. `response_mime_type="application/json"` is the analogue of the local client's `fmt="json"` — it lets us honor `generate(prompt, fmt="json")` on the Gemini path.

**Alternatives considered**: raw REST via `requests` (rejected — reimplements auth/retries/streaming the SDK already handles); `google-generativeai` (rejected — legacy).

## Decision 2: Match the two-method duck interface, not the full LocalClient

**Decision**: `GeminiClient` implements exactly `generate(prompt, fmt=None, options=None) -> str` and `ready() -> bool` — the ONLY methods `ChatReasoningProvider` calls on its `local` client (verified: `chat_reasoning.py` calls `self.local.ready()` then `self.local.generate(self._render(messages), fmt="json")`).

**Rationale**: This makes `GeminiClient` a drop-in for `ChatReasoningProvider(local=…)` with zero change to the provider or the session loop. We do NOT need `chat()`, `warm()`, `available()`, `supports_tools()`, or the Ollama tool-calling path.

**Mapping**:
- `generate(prompt, fmt, options)` → `client.models.generate_content(model, contents=prompt, config=…)`; `fmt=="json"` → `response_mime_type="application/json"`; return `resp.text`. Errors (auth, network, quota) wrap into a typed error the caller surfaces.
- `ready()` → returns True iff the SDK is importable AND a key is configured. It performs **no network/paid call** (a probe would cost money and break offline use). "Reachability" of a hosted API is assumed; a bad key surfaces on the first real turn (edge case in spec).

**Alternatives considered**: defining a shared `ReasoningClient` Protocol (deferred — YAGNI for two concrete clients; duck typing suffices and the annotation on `ChatReasoningProvider.local` is non-enforcing).

## Decision 3: Lazy SDK import + optional-dependency extra (Principle V)

**Decision**: `google-genai` is declared only under `[project.optional-dependencies] gemini` and imported INSIDE `GeminiClient` methods/constructor (`from google import genai`), guarded to raise a typed `GeminiUnavailable` with an install hint when absent. `sr_agent/llm_core/gemini_client.py` has NO top-level `google` import.

**Rationale**: The kernel must import and the full suite must pass with the SDK absent (FR-007). A lazy import keeps `gemini_client` importable everywhere; only actually constructing/using a client needs the SDK. This mirrors how `claude_client.py` tolerates a missing key (errors clearly at construction) but goes further (the dep itself is optional). An architecture test asserts no top-level SDK import.

**Alternatives considered**: adding `google-genai` to base `dependencies` (rejected — would make a paid-provider SDK a hard requirement, violating Principle V's spirit even though import ≠ call).

## Decision 4: Key resolution — UI over env, write-only

**Decision**: `config.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")` (optional, like `anthropic_api_key`). `ModelConfig` holds the optional UI key in the existing write-only `_paid_key`. Effective key = `_paid_key or config.gemini_api_key`. The key is never in `public()`, never persisted, never logged (existing pattern; `public()` already exposes only `has_paid_key`).

**Rationale**: Satisfies FR-002 (both sources, UI precedence) and FR-003 (write-only) by reusing the spec-005 mechanism that already got this right.

## Decision 5: Curated static model list (offline-deterministic)

**Decision**: Ship a small curated list of flash-tier models as the dropdown source, e.g. `["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-3.5-flash"]` (simpler/cheaper tier first), exposed via `GET /api/model/models`. The default selection is the first entry.

**Rationale**: FR-005 needs "a list of selectable models" favoring the cheaper tier. A curated constant is offline-testable, deterministic, and refreshable without a spec change (Assumptions allow this). A LIVE `client.models.list()` needs a key + network and would make the endpoint non-deterministic/paid — deferred as a possible enhancement, out of scope for v1.

**Alternatives considered**: live `client.models.list()` (deferred — network/paid, non-deterministic, not needed for the "pick something simpler" UX).

## Decision 6: Trust status is already enforced — no new code

**Decision**: Do not add any `SourceType` tagging for Gemini output; rely on `ChatTurn` (`models/chat.py:71`) defaulting `source_type=external_llm_output` and `_FORBIDDEN_TURN_TIERS` blocking human/inference tiers.

**Rationale**: The reasoning turn is wrapped identically regardless of which client produced the text, so Gemini output is `external_llm_output` by construction (FR-006). We add a test asserting it, but no production code.

## Backend selector naming (reconciled — /speckit-analyze C1)

**Keep the existing backend value `"paid"`** — do NOT rename to `"gemini"`. An existing test (`tests/frontend/test_no_paid_api.py:37,73`) already pins `{"local","paid"}` and posts `backend="paid"`; renaming would regress green tests for no functional gain. Instead: the `"paid"` backend (previously an unwired stub) now BUILDS a `GeminiClient` — the only paid provider today. The frontend Provider dropdown is *labeled* "Gemini" but sends `backend="paid"`. This preserves the generic "explicit paid selection, never a silent fallback" invariant the constitution test guards, and defers a per-provider discriminator until a second paid provider actually exists (YAGNI). Validation set stays `{"local","paid"}`.
