# Contract: Gemini provider surfaces

## `GeminiClient` (library, `sr_agent/llm_core/gemini_client.py`)

```python
from sr_agent.llm_core.gemini_client import GeminiClient, GeminiUnavailable, SIMPLE_MODELS

c = GeminiClient(api_key="…", model="gemini-2.5-flash")
c.ready() -> bool                                   # True iff SDK importable AND key non-empty; NO network call
c.generate(prompt, fmt="json", options=None) -> str # resp.text; fmt="json" → response_mime_type=application/json
# SDK missing OR key empty → GeminiUnavailable(actionable message)
```

**Guarantees**:
- No top-level `google` import — `import sr_agent.llm_core.gemini_client` succeeds with `google-genai` absent.
- `generate` returns a plain `str`; on SDK/auth/network failure raises a typed error (not a bare SDK exception leaking through).
- `ready()` never makes a paid/network call.

## Frontend backend

- `GET /api/model/config` → `{endpoint, model, backend, has_paid_key}` — **never** the key value (unchanged).
- `POST /api/model/config` (unchanged shape) accepts `{endpoint?, model?, backend?, paid_key?}`; `backend ∈ {"local","paid"}` (unchanged set; 400 on other values); `paid_key` is stored write-only.
- `GET /api/model/models` (NEW) → `{"models": [...flash-tier...], "selected": "<current or default>"}`.
- Selecting `backend="paid"` makes the next session build a `GeminiClient` via `CONFIG.reasoning_client()`; `backend="local"` builds a `LocalClient` (unchanged). No implicit fallback between them.

## Settings.svelte

- Provider select: `Local` | `Gemini` (the "Gemini" option sends `backend="paid"`).
- When Gemini: show the model dropdown (from `/api/model/models`) and the existing write-only key field.
- Saving posts to `/api/model/config`; the key field is send-only (the UI shows only "key set", never the value).

## Tests assert

- **Client** (`tests/unit/test_gemini_client.py`, mocked SDK): `ready()` true only with SDK+key; `generate` returns the mocked `resp.text` and passes `response_mime_type=application/json` when `fmt="json"`; `GeminiUnavailable` when the SDK import fails or key empty.
- **Config wiring** (`tests/unit/test_model_config_gemini.py`): key precedence `_paid_key` over `config.gemini_api_key`; env fallback; neither → `reasoning_client()` for `"paid"` yields a client whose `ready()` is False (disabled state); `public()` never contains the key; `backend` validation rejects unknown values (still `{"local","paid"}`); `reasoning_client()` returns a `GeminiClient` for `"paid"` and a `LocalClient` for `"local"`.
- **Trust status** (`tests/integration/test_gemini_turn_source_type.py`): a chat turn produced via a Gemini-backed provider is recorded as `external_llm_output` (never `human_input`).
- **Optional** (`tests/architecture/test_gemini_optional.py`): `sr_agent.llm_core.gemini_client` has no top-level `google`/`google.genai` import (AST); importing the core packages succeeds without `google-genai`; the full suite passes with the SDK absent.
