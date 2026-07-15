# Data Model: Report→PoC Batch on a Hosted Model (spec 022)

No persistent storage. In-memory client + CLI config; the change is a thin seam in `scripts/poc_queue_runner.py`.

## Entity: generation client (existing, now polymorphic)

The object the harness calls `generate()`/`ready()` on. One of:

| Provider | Class | Key source | Default model |
|----------|-------|-----------|---------------|
| `local` (default) | `LocalClient` | n/a (Ollama host) | `MODEL` (existing) |
| `openrouter` | `OpenRouterClient` (spec 020) | `OPENROUTER_API_KEY` (env) | `z-ai/glm-5.2` |
| `gemini` | `GeminiClient` (spec 018) | `GEMINI_API_KEY` (env) | `SIMPLE_MODELS[0]` |

All implement `generate(prompt, fmt=None, options=None) -> str` and `ready() -> bool`. Only these two are used on the marker path.

## New pure helpers (in `poc_queue_runner.py`)

- `build_generation_client(provider: str, model: str, host: str, timeout: float) -> LocalClient | OpenRouterClient | GeminiClient` — the factory above; `model=""` → the provider default.
- `resolve_lookup_protocol(provider: str, requested: str) -> str` — `local` → `requested`; hosted+`tool` → raise `SystemExit`/clear error; hosted+`auto|marker` → `"marker"`.
- `hosted_ready_error(provider: str, client, effective_key: str) -> str | None` — `None` if ready; else a clear message: `""`/no key → "no <PROVIDER>_API_KEY configured"; gemini + key present + `not ready()` → "install google-genai". No network call.

## CLI (edited)

| Arg | Change |
|-----|--------|
| `--provider` | NEW — `{local,openrouter,gemini}`, default `local`. |
| `--model` | unchanged — overrides the provider's default model. |
| `--host` | unchanged — used only by `local`. |
| `--lookup-protocol` | unchanged values; hosted forces `marker` and rejects `tool` (via `resolve_lookup_protocol`). |

## `main()` startup flow (edited)

1. `provider = args.provider`; `client = build_generation_client(provider, args.model, args.host, GEN_TIMEOUT_S)`.
2. If `provider == "local"`: today's path — keep-alive thread (`available()`), `warm()`, `ready()`.
3. Else (hosted): NO keep-alive/warm/available; `err = hosted_ready_error(provider, client, effective_key)`; if `err`: log abort + `sys.exit(1)`.
4. `protocol = resolve_lookup_protocol(provider, args.lookup_protocol)` (hosted → marker; explicit tool+hosted → abort).
5. The rest of the run (extract → per-finding draft/fix/gate/verify) is unchanged, driven by `client.generate`.

## Trust / invariants (unchanged)

- Hosted output is untrusted external LLM output; the `_poc_defects` structural gate + vacuous-pass guard remain the arbiters; a PASS is a mechanical reproduction only.
- The key is env-sourced, never in argv/log/result.
- Target/report/generated PoCs stay outside the agent repo (existing harness behavior).
