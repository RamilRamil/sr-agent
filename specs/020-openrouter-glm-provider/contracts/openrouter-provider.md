# Contract: OpenRouter provider surfaces

## `OpenRouterClient` (library, `sr_agent/llm_core/openrouter_client.py`)

```python
from sr_agent.llm_core.openrouter_client import (
    OpenRouterClient, OpenRouterUnavailable, OPENROUTER_MODELS,
)

c = OpenRouterClient(api_key="…", model="z-ai/glm-5.2")
c.ready() -> bool                                    # bool(api_key); NO network call
c.generate(prompt, fmt="json", options=None) -> str  # choices[0].message.content; fmt="json" → response_format json_object
# empty key OR failed/unparseable call → OpenRouterUnavailable
```

**Guarantees**:
- Uses only stdlib (`urllib`, `json`) + our own modules — NO new package, NO `openai` SDK (asserted by an architecture test).
- `generate` returns a plain `str`; on HTTP/network/parse failure raises the typed `OpenRouterUnavailable` (no raw urllib error leaking).
- `ready()` never makes a paid/network call.

## Frontend backend

- `GET /api/model/config` (main) / `GET /api/model/additional` — unchanged shape; never the key.
- `POST /api/model/config` — `backend ∈ {"local","paid","openrouter"}` (400 otherwise).
- `POST /api/model/additional` — `backend ∈ {"local","paid","openrouter","off"}` (400 otherwise).
- `GET /api/model/models` → `{"models": [...gemini...], "openrouter": [...glm...], "selected": "<current or default>"}`.
- Selecting `backend="openrouter"` makes the next session build an `OpenRouterClient` via `reasoning_client()`/`additional_client()`; no implicit fallback.

## Settings.svelte

- Main + Additional method selects gain an **OpenRouter (GLM)** option.
- When OpenRouter: show the GLM model dropdown (from the `openrouter` list) and a note that the key comes from `OPENROUTER_API_KEY` (env); the write-only key field remains optional.

## Tests assert

- **Client** (`tests/unit/test_openrouter_client.py`, mocked `urllib.request.urlopen`): `generate("p", fmt="json")` returns the fake `choices[0].message.content` and the request body carried `response_format={"type":"json_object"}` + the model + `Authorization: Bearer` header; `generate` without `fmt` omits `response_format`; `ready()` True with a key, False without; empty key or a failing HTTP call → `OpenRouterUnavailable`.
- **Config wiring** (`tests/unit/test_model_config_openrouter.py`): `set_config(backend="openrouter")` accepted, `nonsense` rejected; `effective_openrouter_key()` = `_paid_key` over `config.openrouter_api_key`; `reasoning_client()` for `"openrouter"` returns an `OpenRouterClient` with that key+model; `additional_client()` for `"openrouter"` is `None` without a key; `public()` never contains the key.
- **No new dep** (`tests/architecture/test_openrouter_no_dep.py`, AST): `openrouter_client.py`'s top-level imports are only stdlib (`urllib`, `json`, …) + `sr_agent.*` — no `openai`, `requests`, `httpx`, `anthropic`, `google`.
- **Offline/optional** (reuse full suite): no `OPENROUTER_API_KEY`, OpenRouter unused → suite green; `test_no_paid_api.py` stays green.
