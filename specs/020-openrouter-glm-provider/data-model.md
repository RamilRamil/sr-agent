# Data Model: OpenRouter / GLM Provider (spec 020)

No persistent storage. In-memory client + config.

## Entity: OpenRouterClient (new, `sr_agent/llm_core/openrouter_client.py`)

| Field | Type | Notes |
|-------|------|-------|
| `api_key` | `str` | Bearer key (env or UI). Non-empty required to use. |
| `model` | `str` | OpenRouter slug; defaults to `OPENROUTER_MODELS[0]` (`z-ai/glm-5.2`). |

**Module constants**:
- `OPENROUTER_MODELS: list[str]` — curated slugs, GLM first: `["z-ai/glm-5.2"]` (refreshable).
- `BASE_URL = "https://openrouter.ai/api/v1/chat/completions"`.

**Methods** (duck-compatible with LocalClient/GeminiClient):
- `generate(prompt, fmt=None, options=None) -> str` — POST via `urllib`; `fmt=="json"` adds `response_format={"type":"json_object"}`; returns `choices[0].message.content`. Network/HTTP/parse errors → `OpenRouterUnavailable`. Empty key → `OpenRouterUnavailable`.
- `ready() -> bool` — `bool(self.api_key)`; no network call.

**Exception**: `OpenRouterUnavailable(Exception)` — empty key or a failed/unparseable call.

## Entity: Config (edited, `sr_agent/config.py`)

| Field | Change |
|-------|--------|
| `openrouter_api_key: str` | NEW — `os.environ.get("OPENROUTER_API_KEY", "")`, optional (empty default). |

## Entity: ModelConfig slot (edited, `frontend/backend/model_config.py`)

| Aspect | Change |
|--------|--------|
| `backend` values | MAIN `{"local","paid","openrouter"}`; ADDITIONAL `{"local","paid","openrouter","off"}`. |
| `effective_openrouter_key()` | NEW — `self._paid_key or config.openrouter_api_key` (UI over env). |
| `reasoning_client()` | NEW branch: `backend == "openrouter"` → `OpenRouterClient(api_key=effective_openrouter_key(), model=self.model or OPENROUTER_MODELS[0])`. |
| `additional_client()` | NEW branch: `backend == "openrouter"` → `None` if no key, else the `OpenRouterClient`. |
| `public()` | unchanged shape `{endpoint, model, backend, has_paid_key}` — never the key. |

## Entity: Model list endpoint (edited)

`GET /api/model/models` → `{"models": SIMPLE_MODELS, "openrouter": OPENROUTER_MODELS, "selected": ...}` — the UI shows the right list per selected method. Read-only, no key.

## Trust / relationships

- OpenRouter output → `ChatTurn` (unchanged) → `external_llm_output`. No new trust code.
- `reasoning_client()`/`additional_client()` are consumed by `sessions.py` (spec 019) — a method change takes effect on the next session build.
- The key never enters `public()`, a log, or disk (FR-004) — enforced by the write-only design + a test.
