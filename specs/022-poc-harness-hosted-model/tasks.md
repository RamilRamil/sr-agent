# Tasks: Run the Report→PoC Batch on a Hosted Model

**Input**: Design documents from `specs/022-poc-harness-hosted-model/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/poc-harness-provider.md

**Tests**: INCLUDED — spec mandates them (FR-011; the opt-in/safety-stop invariants must be pinned).

**Organization**: by user story. All change is in `scripts/poc_queue_runner.py` + one test file + docs.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different file, no dependency on an incomplete task)
- Paths are repo-root-relative

---

## Phase 1: Foundational — pure helpers (Priority: P1) 🎯

**Purpose**: the provider factory + protocol/readiness logic, extracted as pure functions so US1/US2 are testable offline without `main()` or a real model.

- [X] T001 In `scripts/poc_queue_runner.py`: import `OpenRouterClient`, `OPENROUTER_MODELS` (from `sr_agent.llm_core.openrouter_client`) and `GeminiClient`, `SIMPLE_MODELS` (from `sr_agent.llm_core.gemini_client`). Add `build_generation_client(provider, model, host, timeout) -> LocalClient | OpenRouterClient | GeminiClient`: `local` → `LocalClient(model=model or MODEL, host=host, timeout_s=timeout)` (today's build); `openrouter` → `OpenRouterClient(api_key=os.environ.get("OPENROUTER_API_KEY",""), model=model or OPENROUTER_MODELS[0])`; `gemini` → `GeminiClient(api_key=os.environ.get("GEMINI_API_KEY",""), model=model or SIMPLE_MODELS[0])`.
- [X] T002 Add `resolve_lookup_protocol(provider, requested) -> str`: `local` → `requested` unchanged; hosted + `requested == "tool"` → raise a clear error (a dedicated `ProviderStartupError`, or `SystemExit` with a message) "hosted provider has no tool-calling; use --lookup-protocol marker"; hosted + `auto`/`marker` → `"marker"`.
- [X] T003 Add `hosted_ready_error(provider, client) -> str | None`: `None` when the hosted client is ready; when the effective key is empty → `"no {OPENROUTER_API_KEY|GEMINI_API_KEY} configured for provider '{provider}'"`; when provider is `gemini`, the key IS present, but `client.ready()` is False → `"Gemini selected but google-genai is not installed — pip install '.[gemini]'"`. No network call. (Reuse `client.effective_*`/`api_key` to detect the key.)

**Checkpoint**: helpers importable; each returns the right value for local/openrouter/gemini inputs.

---

## Phase 2: User Story 1 + 2 wiring — CLI + startup (Priority: P1)

**Goal**: `--provider` selects the client; hosted path skips Ollama-only startup and gates on readiness + marker; local path byte-identical.

### Tests (write first)

- [X] T004 [P] [US1] Create `tests/unit/test_poc_harness_provider.py`: `build_generation_client("openrouter","", host, t)` → `OpenRouterClient` with `model == OPENROUTER_MODELS[0]` ("z-ai/glm-5.2") and `api_key` from a monkeypatched `OPENROUTER_API_KEY`; `"gemini"` → `GeminiClient` with `SIMPLE_MODELS[0]`; `"local"` → `LocalClient` with `model or MODEL`. **C2:** an EMPTY `model` arg yields the per-provider default for each (openrouter→GLM, gemini→flash, local→`MODEL`), and an explicit `--model` override is respected. A mocked `generate`-only fake used through the client returns text (proves the marker path needs only `generate`).
- [X] T005 [P] [US2] In the same test file: `resolve_lookup_protocol("openrouter","tool")` raises (clear message); `("openrouter","auto")`, `("gemini","marker")` → `"marker"`; `("local","auto")` → `"auto"`. `hosted_ready_error` — no key → the "no <KEY> configured" message; key present (monkeypatched) → `None`; gemini + key + fake client `ready()` False → the "install google-genai" message.

### Implementation

- [X] T006 [US1] In `scripts/poc_queue_runner.py` argparse: add `ap.add_argument("--provider", choices=["local","openrouter","gemini"], default="local", help="model provider driving the batch (hosted = opt-in, key from env)")`. **C2:** change the existing `--model` default from `MODEL` to `""` (empty) — so a hosted provider falls back to ITS default model (not the local qwen slug). `build_generation_client` maps empty→per-provider default (local→`MODEL`, openrouter→`OPENROUTER_MODELS[0]`, gemini→`SIMPLE_MODELS[0]`); confirm any other read of `args.model` tolerates `""` (local branch uses `model or MODEL`).
- [X] T007 [US1] In `main()`: replace the direct `client = LocalClient(...)` with `client = build_generation_client(args.provider, args.model, args.host, GEN_TIMEOUT_S)`. For `args.provider == "local"` keep today's startup EXACTLY (keep-alive thread → `warm()` → `ready()`). For a hosted provider: DO NOT start the keep-alive thread and DO NOT call `warm()`/`available()`; instead `err = hosted_ready_error(args.provider, client)`; if `err`: `log({"event":"abort","reason":err})` + `sys.exit(1)`. **C1:** compute the resolved protocol FIRST — `requested = resolve_lookup_protocol(args.provider, args.lookup_protocol)` (catch its error → clean `sys.exit(1)`) — and pass THAT into the existing call: `protocol_mode, protocol_source = _select_protocol(requested, client)`. NEVER pass the raw `args.lookup_protocol` for a hosted provider, because `_select_protocol` calls `client.supports_tools()` on the `auto`/`tool` branches and hosted clients lack it (AttributeError). Hosted always resolves to `"marker"`, which `_select_protocol` returns immediately without touching `supports_tools()`.
- [X] T008 [US1] Widen the `client: LocalClient` annotations on the marker/draft/fix functions (`draft`, `fix`, `_traced_round_trip`/marker round-trip, `extract_tasks`, `_select_protocol` — wherever typed `LocalClient`) to `LocalClient | OpenRouterClient | GeminiClient`. No behavior change (only `generate` is used on the marker path).

**Checkpoint**: `pytest tests/unit/test_poc_harness_provider.py -q` green; `--provider local` unchanged; hosted forces marker + safe startup stops.

---

## Phase 3: Polish & Cross-Cutting

- [X] T009 [P] Update `docs/roadmap.md` (spec 022 landing: the report→PoC batch now runs on a capable hosted model — GLM via OpenRouter, Gemini — over the whole report via the marker path; opt-in `--provider`, default local unchanged; key env-only; PASS still a mechanical reproduction — `_poc_defects`/vacuous-pass guard intact; CLI path, frontend trigger later) and `RUN_FRONTEND.local.md` follow-up section (replace the "batch only talks to LocalClient" note with the new `--provider openrouter`/`gemini` command).
- [X] T010 Final gate: full suite offline (no `OPENROUTER_API_KEY`/`GEMINI_API_KEY`, no network) `pytest -q` green, zero regressions (existing `poc_queue_runner` tests unchanged); `ruff check scripts/poc_queue_runner.py tests/unit/test_poc_harness_provider.py` clean.

---

## Dependencies & Execution Order

- **Foundational (T001-T003)** → the helpers; block everything.
- **Tests (T004-T005)** depend on T001-T003.
- **Wiring (T006-T008)** depends on T001-T003; T007 depends on T006 (arg) + T002/T003 (helpers).
- **Polish (T009-T010)** last.

## Parallel Opportunities

- T004 / T005 [P] (same new file, but independent test groups — write together).
- T009 (docs) [P] once behavior is settled.

## Implementation Strategy

MVP = Foundational + wiring (T001-T008): `--provider openrouter` runs the whole report→PoC batch on GLM through the existing pipeline, with safe startup stops. The pure helpers make the opt-in + safety-stop invariants testable offline before the live GLM run.

**Total tasks**: 10 (Foundational 3, Tests 2, Wiring 3, Polish 2).
