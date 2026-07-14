# Quickstart: Optional Gemini Model Provider (spec 018)

An OPTIONAL, operator-selected hosted-model backend. The core agent runs on the local model / relay without it.

## Enable it

```bash
# 1. install the optional SDK (only if you want Gemini)
pip install '.[gemini]'          # or: uv pip install google-genai

# 2. provide a key — either way works
export GEMINI_API_KEY=…          # env, OR
# … paste the key into the frontend Settings → Gemini key field (UI key wins over env)
```

With neither the SDK nor a key, everything still runs on local/relay; selecting Gemini shows a clear "unavailable" message.

## Use it from the UI

1. Open **Settings**.
2. Provider → **Gemini**.
3. Pick a model from the dropdown (cheaper flash-tier first, e.g. `gemini-2.5-flash`).
4. (If not using the env key) paste the API key into the write-only key field.
5. Run a session — turns are now served by the chosen Gemini model. Switch Provider back to **Local** to return to the local model.

## Integration scenarios (→ acceptance criteria)

1. **US1 / SC-001** — configure key + select Gemini + pick model + run a turn, all from the UI, no restart.
2. **US2 / SC-005** — env-only key works; UI key overrides env; neither → clear disabled state.
3. **US2 / SC-002** — `GET /api/model/config` and every status surface report only `has_paid_key`, never the key; the key is in no log or file.
4. **US3 / SC-003** — with `google-genai` uninstalled and no key, `pytest -q` is green and the agent runs on local/relay.
5. **US3 / SC-004** — Gemini is used only when `backend="gemini"` is explicitly set; never an implicit fallback.

## Run the tests (offline, no key, no network)

```bash
pytest tests/unit/test_gemini_client.py tests/unit/test_model_config_gemini.py \
       tests/integration/test_gemini_turn_source_type.py \
       tests/architecture/test_gemini_optional.py -q
```

All use a mocked SDK and assert the security posture (write-only key, external_llm_output, optional dependency).
