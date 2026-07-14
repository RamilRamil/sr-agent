# Tasks: Optional Gemini Model Provider

**Input**: Design documents from `specs/018-gemini-provider/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/gemini-provider.md

**Tests**: INCLUDED — spec mandates them (FR-011 offline tests; US3 optional-dependency guarantee).

**Organization**: by user story. US2 (key handling) and US3 (optional/isolated) are foundational-heavy P1s; US1 (run a turn on Gemini) is the visible MVP that sits on top.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different file, no dependency on an incomplete task)
- Paths are repo-root-relative

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Add the optional extra to `pyproject.toml`: `[project.optional-dependencies] gemini = ["google-genai>=1.0.0"]` (base `dependencies` unchanged — Gemini SDK must NOT become a runtime dep).
- [X] T002 [P] Add `gemini_api_key: str` to `Config` and set `gemini_api_key=os.environ.get("GEMINI_API_KEY", "")` in `load_config()` in `sr_agent/config.py` (optional, empty default, mirroring `anthropic_api_key`); add the brief "optional, core runs without it (Constitution V)" comment.

**Checkpoint**: `import sr_agent.config` works; the extra is declared but not installed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the `GeminiClient` itself — every user story depends on it existing and being import-safe.

- [X] T003 Create `sr_agent/llm_core/gemini_client.py`: module docstring (optional paid provider, lazy SDK, output is external_llm_output via ChatTurn, never a fallback); `SIMPLE_MODELS = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-3.5-flash"]`; `GeminiUnavailable(Exception)`; a `_sdk()` helper that does `from google import genai` (+ `from google.genai import types`) lazily and raises `GeminiUnavailable("install google-genai: pip install '.[gemini]'")` on `ImportError`. **NO top-level `google` import.**
- [X] T004 Add `GeminiClient` dataclass/class (`api_key: str`, `model: str = SIMPLE_MODELS[0]`) with `ready() -> bool` (True iff `_sdk()` importable AND `api_key` non-empty; catch `GeminiUnavailable` → False; **no network call**) and `generate(prompt, fmt=None, options=None) -> str` (build `genai.Client(api_key=…)`, call `client.models.generate_content(model=self.model, contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json") if fmt=="json" else None)`, return `resp.text`; wrap SDK/auth/network exceptions into `GeminiUnavailable` with a clear message; empty key → `GeminiUnavailable`).

**Checkpoint**: `import sr_agent.llm_core.gemini_client` succeeds with `google-genai` absent; `GeminiClient("", ...).ready()` is False.

---

## Phase 3: User Story 3 — Optional & non-breaking (Priority: P1)

**Goal**: prove Gemini is optional — core imports/tests pass with the SDK absent and no key; no top-level SDK import.

**Independent Test**: with `google-genai` uninstalled and no `GEMINI_API_KEY`, `pytest -q` is green; the guard test fails if a top-level `google` import is added.

### Tests for US3

- [X] T005 [P] [US3] Create `tests/architecture/test_gemini_optional.py` (AST-based): assert `sr_agent/llm_core/gemini_client.py` has NO top-level `import google...` / `from google...` (only inside a function); assert `import sr_agent.llm_core.gemini_client` and `import sr_agent.cli` succeed in-process (SDK not required to import); assert `GeminiClient("", model=SIMPLE_MODELS[0]).ready() is False`.

### Implementation for US3

- [X] T006 [US3] Verify/adjust so nothing in `sr_agent/**` imports `google` at module top level (the lazy `_sdk()` is the only import site). No production code beyond T003/T004 should be needed; this task is the guard-green confirmation.

**Checkpoint**: `tests/architecture/test_gemini_optional.py` passes; full suite still green with SDK absent.

---

## Phase 4: User Story 2 — Key by env OR UI, UI wins, write-only (Priority: P1)

**Goal**: key resolution (UI over env), never-exposed key, provider/model wiring in `ModelConfig`.

**Independent Test**: `_paid_key` beats `config.gemini_api_key`; env fallback; neither → gemini `reasoning_client().ready()` is False; `public()` never contains the key.

### Tests for US2

- [X] T007 [P] [US2] Create `tests/unit/test_model_config_gemini.py`: `set_config(backend="paid")` accepted, unknown backend rejected (ValueError, set still `{"local","paid"}`); `effective_gemini_key()` returns `_paid_key` when set else `config.gemini_api_key` (monkeypatch env/config); with a key, `reasoning_client()` for `"paid"` returns a `GeminiClient` with that key+model; `backend="local"` returns a `LocalClient`; with no key, the `"paid"` `reasoning_client().ready()` is False; `CONFIG.public()` keys are exactly `{endpoint, model, backend, has_paid_key}` and contain no key value even after setting one.

### Implementation for US2

- [X] T008 [US2] Edit `frontend/backend/model_config.py`: KEEP `backend` valid set `{"local","paid"}` (analyze C1 — do NOT rename; existing `tests/frontend/test_no_paid_api.py` pins it); update the comment so `"paid"` documents "builds a GeminiClient — the only paid provider today; UI labels it Gemini"; add `effective_gemini_key() -> str` (`self._paid_key or config.gemini_api_key`); add `reasoning_client()` that returns `local_client()` for `"local"` and `GeminiClient(api_key=self.effective_gemini_key(), model=self.model or SIMPLE_MODELS[0])` for `"paid"`. Keep `_paid_key` write-only and `public()` shape unchanged (still only `has_paid_key`).

**Checkpoint**: `tests/unit/test_model_config_gemini.py` passes; key never in `public()`.

---

## Phase 5: User Story 1 — Run a session on a Gemini model from the UI (Priority: P1) 🎯 MVP

**Goal**: the operator-visible path — select Gemini + a model, run a turn served by it, output is external_llm_output.

**Independent Test**: a chat turn built via a Gemini-backed provider (mocked SDK) is recorded as `external_llm_output`; the models endpoint lists the flash tier; Settings offers provider+model+key.

### Tests for US1

- [X] T009 [P] [US1] Create `tests/unit/test_gemini_client.py` (mocked SDK — inject a fake `google.genai` into `sys.modules`): `generate("p", fmt="json")` returns the fake `resp.text` and the call passed `response_mime_type="application/json"`; `generate` without `fmt` omits JSON mode; `ready()` True with SDK+key, False without key; a fake SDK that raises on import → `ready()` False and `generate` raises `GeminiUnavailable`.
- [X] T010 [P] [US1] Create `tests/integration/test_gemini_turn_source_type.py`: drive one chat turn through `ChatReasoningProvider` with a fake reasoning provider/GeminiClient (reuse the sessions `provider_factory` test seam) and assert the persisted `ChatTurn.source_type == SourceType.external_llm_output` (never `human_input`).

### Implementation for US1

- [X] T011 [US1] Edit `frontend/backend/sessions.py`: build the provider's client from `CONFIG.reasoning_client()` instead of `CONFIG.local_client()` (line ~81), so an explicit `backend="paid"` selection takes effect on the next session build. **C2:** widen `ChatReasoningProvider.local`'s annotation to `LocalClient | GeminiClient` (or add a one-line comment noting the duck contract: only `ready()`/`generate()` are used) so the Gemini path isn't misread as type-wrong.
- [X] T012 [US1] Add `GET /api/model/models` to `frontend/backend/app.py` returning `{"models": SIMPLE_MODELS, "selected": CONFIG.model or SIMPLE_MODELS[0]}` (read-only, no key). Confirm the existing `POST /api/model/config` already carries `backend`/`model`/`paid_key` (it does — no change needed there).
- [X] T013 [US1] Edit `frontend/ui/src/panels/Settings.svelte`: add a Provider select labeled `Local` / `Gemini` (the "Gemini" option sends `backend="paid"`); when Gemini, show a model `<select>` populated from `GET /api/model/models` and the existing write-only key field; on save POST `{backend, model, paid_key}` to `/api/model/config`. The key field is send-only (show "key set", never the value).

**Checkpoint**: US1 tests pass; from the UI an operator can select Gemini + model + key and a turn runs on it.

---

## Phase 6: Polish & Cross-Cutting

- [X] T014 [P] Update `docs/roadmap.md`: spec 018 landing entry — the provider, env-vs-UI key precedence (UI wins), curated flash-tier model list, and the Principle-V posture (optional extra, lazy import, explicit selection, graceful absence; never a fallback; output stays external_llm_output).
- [X] T015 Final gate: full suite offline with `google-genai` ABSENT (`pytest -q`) is green with zero regressions; `ruff check` clean on all new/edited Python (`sr_agent/llm_core/gemini_client.py`, `sr_agent/config.py`, `frontend/backend/model_config.py`, `frontend/backend/app.py`, `frontend/backend/sessions.py`, the new tests).

---

## Dependencies & Execution Order

- **Setup (T001-T002)** → base.
- **Foundational (T003-T004)** → `GeminiClient` exists + import-safe; blocks all stories.
- **US3 (T005-T006)** depends on Foundational; proves the optional guarantee — do early so the safety net is in place.
- **US2 (T007-T008)** depends on Foundational (needs `GeminiClient` + `SIMPLE_MODELS`).
- **US1 (T009-T013)** depends on Foundational + US2 (`reasoning_client()`); the visible MVP.
- **Polish (T014-T015)** last.

## Parallel Opportunities

- T002 [P] alongside T001 (different files).
- Test-creation tasks T005 / T007 / T009 / T010 are all [P] (different files) once their targets exist.
- T014 [P] (docs) alongside code once behavior is settled.

## Implementation Strategy

MVP = Setup + Foundational + US2 + US1 (a working, key-safe, UI-selectable Gemini turn). US3's guard test is written early (T005) to lock the optional/no-paid-dependency guarantee from the start. Each story is independently testable per its Independent Test.

**Total tasks**: 15 (Setup 2, Foundational 2, US3 2, US2 2, US1 5, Polish 2).
