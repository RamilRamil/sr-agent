# Data Model: Optional Gemini Model Provider (spec 018)

No persistent storage. The entities are in-memory/config objects.

## Entity: GeminiClient (new, `sr_agent/llm_core/gemini_client.py`)

A reasoning client duck-compatible with `LocalClient` for the two methods the chat provider uses.

| Field | Type | Notes |
|-------|------|-------|
| `api_key` | `str` | Explicit key (from UI or env). Non-empty required to use. |
| `model` | `str` | A Gemini model id; defaults to `SIMPLE_MODELS[0]`. |

**Module constants**:
- `SIMPLE_MODELS: list[str]` — curated flash-tier ids, cheaper first (`gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.0-flash`, `gemini-3.5-flash`).

**Methods**:
- `generate(prompt: str, fmt: str | None = None, options: dict | None = None) -> str` — calls `client.models.generate_content`; `fmt=="json"` → `response_mime_type="application/json"`; returns `resp.text`. Wraps SDK/auth/network errors into `GeminiUnavailable` (or a turn-level error the caller surfaces).
- `ready() -> bool` — True iff the SDK is importable AND `api_key` is non-empty. No network/paid call.

**Exception**: `GeminiUnavailable(Exception)` — raised (with an actionable "install google-genai" / "set a key" message) when the SDK is missing or the key is empty.

**Invariant**: NO top-level `from google import genai`; the import happens lazily inside a helper (`_sdk()`), so the module imports with the SDK absent.

## Entity: ModelConfig (edited, `frontend/backend/model_config.py`)

| Field | Change | Notes |
|-------|--------|-------|
| `backend` | values `"local" | "paid"` (UNCHANGED — "paid" now builds Gemini) | Explicit operator choice; default `"local"`. UI labels "paid" as "Gemini". |
| `model` | unchanged | For `paid`, one of `SIMPLE_MODELS`; `None` → default. |
| `_paid_key` | unchanged (write-only) | The UI-provided Gemini key; overrides env. Never in `public()`. |

**New/changed behavior**:
- `set_config(backend=…)` validates against `{"local","paid"}` (unchanged set).
- `effective_gemini_key() -> str` = `_paid_key or config.gemini_api_key` (UI over env).
- `reasoning_client() -> LocalClient | GeminiClient` — branches on `backend`: `"local"` → existing `local_client()`; `"paid"` → `GeminiClient(api_key=effective_gemini_key(), model=self.model or SIMPLE_MODELS[0])`.
- `public()` unchanged in shape: `{endpoint, model, backend, has_paid_key}` — still no key value.

## Entity: Config (edited, `sr_agent/config.py`)

| Field | Change |
|-------|--------|
| `gemini_api_key: str` | NEW — `os.environ.get("GEMINI_API_KEY", "")`, optional (empty default), mirroring `anthropic_api_key`. |

## Entity: Selectable-models endpoint (new route)

`GET /api/model/models -> {"models": SIMPLE_MODELS, "selected": CONFIG.model or SIMPLE_MODELS[0]}` — read-only, no key involved, drives the UI dropdown.

## Relationships / trust

- Gemini output → `ChatTurn` (unchanged) → `source_type = external_llm_output`. No new trust code; the status is structural.
- `reasoning_client()` is consumed by `frontend/backend/sessions.py` (was `local_client()`); a config change (key/backend/model) takes effect on the next session build (FR-010).
- The key never crosses into `public()`, logs, or disk (FR-003) — enforced by the existing write-only design plus a test.
