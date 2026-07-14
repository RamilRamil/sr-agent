# Quickstart: OpenRouter / GLM Provider (spec 020)

Run a session on GLM 5.2 via OpenRouter — selected from a dropdown, keyed from the environment. Optional; the core agent runs without it.

## Enable it

```bash
# in your .env (or the launch environment) — the key never touches the browser
export OPENROUTER_API_KEY=sk-or-…
```

Use a spend-capped OpenRouter key so any leak is bounded. No package to install (stdlib HTTP).

## Use it from the UI

1. **Settings → Main agent** → Connection = **OpenRouter (GLM)**.
2. Pick the model (defaults to `z-ai/glm-5.2`).
3. Save, then run a session — turns are served by GLM via OpenRouter. Switch back to **Local** any time.

(You can also set the **Additional agent** to OpenRouter for escalations.)

## What stays guaranteed

- OpenRouter is used only when explicitly selected — never a silent fallback.
- Its output is untrusted model output; anything privileged still pauses for your confirmation.
- The key is env-sourced (or a write-only UI override) — never returned by the API, logged, or written to disk.
- With no key, OpenRouter is a clear disabled state; the agent keeps running on local/relay. No new dependency.

## Integration scenarios (→ acceptance)

1. **US1 / SC-001** — select OpenRouter + GLM, run a turn served by it, no restart, no key in the browser.
2. **US2 / SC-005** — env-only key works; a UI key overrides env; neither → clear disabled state.
3. **US2 / SC-002** — every status surface shows only `has_paid_key`, never the key.
4. **US3 / SC-003** — no key + OpenRouter unused → full offline suite green, no new package.

## Run the tests (offline, no key, no network)

```bash
pytest tests/unit/test_openrouter_client.py tests/unit/test_model_config_openrouter.py \
       tests/architecture/test_openrouter_no_dep.py -q
```
