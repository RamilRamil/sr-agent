# Contract: `poc_queue_runner.py` provider selection

## CLI

```
# local (default, unchanged)
python scripts/poc_queue_runner.py --project <target> --report <report.md> [--model qwen3-coder:30b]

# GLM via OpenRouter (env key)
OPENROUTER_API_KEY=sk-or-… \
python scripts/poc_queue_runner.py --project <target> --report <report.md> \
    --provider openrouter --lookup-protocol marker            # marker forced anyway

# Gemini (env key; needs the optional google-genai extra)
GEMINI_API_KEY=… \
python scripts/poc_queue_runner.py --project <target> --report <report.md> \
    --provider gemini
```

- `--provider {local|openrouter|gemini}` (default `local`).
- `--model` overrides the provider default (`z-ai/glm-5.2` for openrouter; a Gemini flash for gemini).
- Hosted providers force the marker protocol; `--lookup-protocol tool` + a hosted provider → clear startup abort.

## Startup behavior

- **local**: unchanged — keep-alive `available()`, `warm()`, `ready()`; abort if Ollama not up.
- **hosted, no key**: abort at startup — "no OPENROUTER_API_KEY / GEMINI_API_KEY configured" — before any finding is processed.
- **gemini, key set, SDK missing**: abort — "install google-genai (pip install '.[gemini]')".
- **hosted, ready**: proceed on the marker protocol.
- The key never appears in argv, a log line, or a result.

## Library surface (pure helpers, unit-tested)

```python
build_generation_client(provider, model, host, timeout)  # -> LocalClient | OpenRouterClient | GeminiClient
resolve_lookup_protocol(provider, requested)             # -> "marker"|"tool"; hosted+"tool" raises
hosted_ready_error(provider, client, effective_key)      # -> str|None (clear message; no network)
```

## Guarantees asserted by tests (`tests/unit/test_poc_harness_provider.py`, offline)

- `build_generation_client("openrouter", "", …)` returns an `OpenRouterClient` with model `z-ai/glm-5.2` and the env key; `"gemini"` → `GeminiClient` with the default flash model; `"local"` → `LocalClient` (unchanged).
- `resolve_lookup_protocol("openrouter", "tool")` raises (clear message); `("openrouter", "auto")` and `("gemini","marker")` → `"marker"`; `("local","auto")` → `"auto"` (unchanged).
- `hosted_ready_error("openrouter", <client no key>, "")` → a "no OPENROUTER_API_KEY" message; with a key → `None`; gemini + key + not-ready → "install google-genai".
- A mocked `generate` client returns text through the client (the marker/draft path uses only `generate`).
- Local-path behavior and the existing harness tests are unchanged (no regressions); the offline suite passes with no hosted key/SDK.
