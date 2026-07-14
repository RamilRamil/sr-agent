# Tasks: OpenRouter Provider with GLM as a Selectable Model

**Input**: Design documents from `specs/020-openrouter-glm-provider/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openrouter-provider.md

**Tests**: INCLUDED — spec mandates them (FR-012; the security/optional invariants must be pinned).

**Organization**: by user story. Mirrors spec 018 (Gemini) with a stdlib HTTP client and "no new package".

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different file, no dependency on an incomplete task)
- Paths are repo-root-relative

---

## Phase 1: Setup / Foundational

- [X] T001 [P] Add `openrouter_api_key: str` to `Config` and `openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", "")` in `load_config()` in `sr_agent/config.py` (optional, empty default, mirroring `gemini_api_key`) with the brief "optional, core runs without it (Constitution V)" note.
- [X] T002 Create `sr_agent/llm_core/openrouter_client.py`: module docstring (optional paid provider, stdlib HTTP, no new package, output external_llm_output via ChatTurn, never a fallback); constants `BASE_URL = "https://openrouter.ai/api/v1/chat/completions"` and `OPENROUTER_MODELS = ["z-ai/glm-5.2"]`; `OpenRouterUnavailable(Exception)`; `OpenRouterClient` (`api_key: str`, `model: str = OPENROUTER_MODELS[0]`) with `ready() -> bool` (`bool(self.api_key)`, no network) and `generate(prompt, fmt=None, options=None) -> str` (urllib POST with `Authorization: Bearer`, body `{model, messages:[{role:"user",content:prompt}]}` + `response_format={"type":"json_object"}` when `fmt=="json"`; return `choices[0].message.content`; empty key or any urllib/HTTP/JSON error → `OpenRouterUnavailable`). **Top-level imports: stdlib only (`json`, `urllib.request`, `urllib.error`) — NO `openai`/`requests`/`httpx`.**

**Checkpoint**: `import sr_agent.llm_core.openrouter_client` works; `OpenRouterClient("").ready()` is False.

---

## Phase 2: User Story 3 — Optional & no new package (Priority: P1)

**Goal**: prove OpenRouter is optional and adds no dependency — core imports/tests pass with no key; the client is stdlib-only.

**Independent Test**: with no `OPENROUTER_API_KEY`, `pytest -q` is green; the guard test fails if a non-stdlib client import is added.

- [X] T003 [P] [US3] Create `tests/architecture/test_openrouter_no_dep.py` (AST-based): assert `sr_agent/llm_core/openrouter_client.py`'s top-level imports contain none of `openai`, `requests`, `httpx`, `anthropic`, `google` (only stdlib + `sr_agent.*`); assert `import sr_agent.llm_core.openrouter_client` succeeds; assert `OpenRouterClient(api_key="").ready() is False`.

**Checkpoint**: guard green; no package added to `pyproject.toml`.

---

## Phase 3: User Story 2 — Env-first key, write-only override (Priority: P1)

**Goal**: key resolution (env primary, UI override), never-exposed key, slot wiring.

**Independent Test**: `_paid_key` beats `config.openrouter_api_key`; env fallback; neither → `additional_client()` for openrouter is `None` / a main openrouter `ready()` is False; `public()` never contains the key.

### Tests for US2

- [X] T004 [P] [US2] Create `tests/unit/test_model_config_openrouter.py`: `set_config(backend="openrouter")` accepted, unknown rejected (ValueError; MAIN set `{"local","paid","openrouter"}`, ADDITIONAL `+"off"`); `effective_openrouter_key()` returns `_paid_key` when set else `config.openrouter_api_key` (monkeypatch `model_config.config`); with a key, `reasoning_client()` for `"openrouter"` returns an `OpenRouterClient` (key+model); `additional_client()` for `"openrouter"` is `None` without a key and an `OpenRouterClient` with one; `public()` keys exactly `{endpoint, model, backend, has_paid_key}`, no key value.

### Implementation for US2

- [X] T005 [US2] Edit `frontend/backend/model_config.py`: extend allowed backend sets (MAIN += `"openrouter"`, ADDITIONAL += `"openrouter"`); add `effective_openrouter_key() -> str` (`self._paid_key or config.openrouter_api_key`); add the `backend == "openrouter"` branch to `reasoning_client()` (→ `OpenRouterClient(api_key=effective_openrouter_key(), model=self.model or OPENROUTER_MODELS[0])`) and to `additional_client()` (→ `None` if no key, else the client). Import `OpenRouterClient`/`OPENROUTER_MODELS`.

**Checkpoint**: `tests/unit/test_model_config_openrouter.py` green; key never in `public()`.

---

## Phase 4: User Story 1 — Select OpenRouter/GLM and run a turn (Priority: P1) 🎯 MVP

**Goal**: the operator-visible path — pick OpenRouter + GLM from the dropdown, turn served by it, output external_llm_output.

**Independent Test**: `generate` (mocked HTTP) returns the message content + sends JSON mode; the models endpoint lists the GLM option; Settings offers OpenRouter as a method.

### Tests for US1

- [X] T006 [P] [US1] Create `tests/unit/test_openrouter_client.py` (monkeypatch `urllib.request.urlopen` to return a fake OpenRouter JSON `{"choices":[{"message":{"content":"OUT"}}]}`, capturing the request): `generate("p", fmt="json")` returns `"OUT"`; the sent body carried `model`, `messages`, and `response_format={"type":"json_object"}`, and the request had an `Authorization: Bearer test-key` header; `generate` without `fmt` omits `response_format`; `ready()` True with a key, False without; empty key raises `OpenRouterUnavailable`; a urllib error → `OpenRouterUnavailable`. **C1:** also assert a `ChatTurn` carrying an OpenRouter-produced `AgentAction` is `SourceType.external_llm_output` and rejects `human_input` (parity with `test_gemini_turn_source_type`), pinning FR-006.

### Implementation for US1

- [X] T007 [US1] Edit `frontend/backend/app.py`: `GET /api/model/models` also returns `"openrouter": list(OPENROUTER_MODELS)` alongside the existing `models`/`selected`. Import `OPENROUTER_MODELS`.
- [X] T008 [P] [US1] Edit `frontend/ui/src/panels/Settings.svelte` + `frontend/ui/src/lib/api.ts`: add an **OpenRouter (GLM)** option to the Main and Additional connection selects; when selected, show the GLM model dropdown (from the endpoint's `openrouter` list) and a note that the key comes from `OPENROUTER_API_KEY` (env); the write-only key field remains optional. Extend the models-endpoint type to carry `openrouter: string[]`.

**Checkpoint**: US1 tests green; from the UI, selecting OpenRouter + GLM runs a turn on it.

---

## Phase 5: Polish & Cross-Cutting

- [X] T009 [P] Update `docs/roadmap.md`: spec 020 landing entry — OpenRouter as a stdlib-HTTP provider (no new package), env-keyed GLM (`z-ai/glm-5.2`, slug verified on live OpenRouter), model dropdown, Principle-V posture (optional/explicit/graceful), external_llm_output, security-stages unchanged.
- [X] T010 Final gate: full suite offline (no `OPENROUTER_API_KEY`, `google-genai` absent) `pytest -q` green, zero regressions (incl. `test_no_paid_api.py`); `ruff check` clean on all new/edited Python.

---

## Dependencies & Execution Order

- **Setup (T001-T002)** → config field + the client; blocks everything.
- **US3 (T003)** depends on T002; the no-dep guard — do early.
- **US2 (T004-T005)** depends on T002 (client + OPENROUTER_MODELS).
- **US1 (T006-T008)** depends on T002 + US2 (`reasoning_client()` branch).
- **Polish (T009-T010)** last.

## Parallel Opportunities

- T001 [P] alongside nothing blocking; T003 / T004 / T006 test-creation tasks are `[P]` (different files) once their targets exist.
- T009 [P] (docs) alongside code once behavior is settled.

## Implementation Strategy

MVP = Setup + US2 + US1 (a working, env-keyed, UI-selectable GLM-via-OpenRouter turn). US3's guard (T003) locks "optional + no new package" from the start.

**Total tasks**: 10 (Setup 2, US3 1, US2 2, US1 3, Polish 2).
