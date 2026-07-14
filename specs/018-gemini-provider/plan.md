# Implementation Plan: Optional Gemini Model Provider

**Branch**: `018-gemini-provider` | **Date**: 2026-07-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/018-gemini-provider/spec.md`

## Summary

Add `GeminiClient` in `sr_agent/llm_core/` as an optional, explicitly-selected reasoning backend that is a drop-in for the existing local client: it implements exactly the two methods `ChatReasoningProvider` calls — `generate(prompt, fmt=None, options=None) -> str` and `ready() -> bool` — using the `google-genai` SDK, imported LAZILY so the kernel module loads with the SDK absent. The frontend's already-present model-config surface (write-only key field + `backend` selector, spec 005) is wired so choosing the Gemini backend builds a `GeminiClient` from the UI key (else the env `GEMINI_API_KEY`); a small curated list of flash-tier models populates a UI dropdown. Gemini output flows through the same `ChatTurn`, which already stamps `external_llm_output` — so the trust status is correct by construction. The whole thing is optional: with `google-genai` uninstalled and no key set, the core agent and full suite run unchanged.

## Technical Context

**Language/Version**: Python 3.11 (project target).

**Primary Dependencies**: NEW optional extra `google-genai` (declared under `[project.optional-dependencies] gemini`, NOT a base/runtime dependency). Imported lazily inside `GeminiClient`. Frontend backend is FastAPI (existing). No other new deps.

**Storage**: none. The Gemini key is held in-memory only (the existing write-only `ModelConfig._paid_key`, or read from env per call); never persisted.

**Testing**: pytest, offline & deterministic. The `google-genai` SDK is mocked (a fake `genai` module injected) — no real key, no network. New unit + architecture tests.

**Target Platform**: the operator frontend process (single-operator) + the `sr_agent` package.

**Project Type**: single project — kernel LLM client + frontend backend wiring + a Svelte settings control.

**Performance Goals**: n/a (a turn's latency is the hosted model's; not a target of this feature).

**Constraints**: Gemini is OPTIONAL and EXPLICIT — never required, never a silent fallback (Principle V, spec-005 FR-021). Key is write-only: never returned by any API, persisted, or logged. `ready()` must NOT make a paid/network call — it checks SDK-importable + key-present only.

**Scale/Scope**: one new client (~120 lines), ~4 edited files (config, model_config, app route, sessions), one Svelte panel, ~5 test files, docs.

## Constitution Check

*GATE: evaluated against the 5 principles. Re-checked after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Secure-Kernel Trust Invariants** | ✅ PASS | Gemini output flows through `ChatTurn`, whose `source_type` defaults to `external_llm_output` and whose `_FORBIDDEN_TURN_TIERS` already blocks `human_input`/`llm_inference` — so Gemini output carries the correct untrusted status by construction, identical to Claude/relay. No change to the `SourceType` ordering (`models/memory.py`). The key is a write-only secret (existing `model_config` pattern): never returned, persisted, or logged. |
| **II. Human Authority** | ✅ PASS | A model backend only. Introduces no privileged/irreversible action, does not touch the confirmation gate or the `REQUIRES_HUMAN_CONFIRMATION` set. |
| **III. Kernel / Pack Separation** | ✅ PASS | `GeminiClient` sits in `sr_agent/llm_core/` beside `local_client.py`/`claude_client.py` — kernel LLM clients, not pack code. No pack coupling. The `google-genai` import is lazy, so the kernel module imports cleanly without the SDK. |
| **IV. Human-Gated Knowledge Promotion** | ✅ PASS | Unrelated to the knowledge loop; adds no self-promoting knowledge path. |
| **V. No Paid-API Dependency** | ✅ PASS | Gemini is paid → made OPTIONAL (SDK is an optional extra, lazily imported, clear error if absent), EXPLICIT (operator must select the `gemini` backend — never an implicit fallback), and GRACEFUL (missing SDK/key → actionable message, local/relay stays usable). The core loop runs on local/relay with the SDK absent and no key set; a guard test proves it. `ready()` performs no paid call. |

**Result: PASS — no violations. Complexity Tracking not required.**

## Project Structure

### Documentation (this feature)

```text
specs/018-gemini-provider/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── gemini-provider.md
└── tasks.md            # /speckit-tasks
```

### Source Code (repository root)

```text
sr_agent/
├── llm_core/
│   └── gemini_client.py     # NEW: GeminiClient (lazy google-genai), generate()/ready(), SIMPLE_MODELS, GeminiUnavailable
└── config.py                # EDIT: add gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

frontend/backend/
├── model_config.py          # EDIT: backend {"local","paid"} (unchanged set; "paid" now builds Gemini); reasoning_client(); key resolution UI>env; models list
└── app.py                   # EDIT: GET /api/model/models (curated list); config route already accepts backend/model/paid_key

frontend/backend/sessions.py # EDIT: build provider from CONFIG.reasoning_client() (was CONFIG.local_client())

frontend/ui/src/panels/
└── Settings.svelte          # EDIT: provider select (local/gemini) + model dropdown from /api/model/models + key field (exists)

pyproject.toml               # EDIT: [project.optional-dependencies] gemini = ["google-genai>=..."]

tests/
├── unit/
│   ├── test_gemini_client.py        # NEW: generate()/ready()/graceful-absence with a mocked SDK
│   └── test_model_config_gemini.py  # NEW: backend wiring, key precedence UI>env, key never in public()
├── integration/
│   └── test_gemini_turn_source_type.py  # NEW: a Gemini-served chat turn is external_llm_output
└── architecture/
    └── test_gemini_optional.py      # NEW: sr_agent imports with google-genai absent; no top-level SDK import

docs/roadmap.md              # EDIT: spec 018 landing entry
```

**Structure Decision**: `GeminiClient` is a kernel LLM client (llm_core), duck-compatible with `LocalClient` for the two methods `ChatReasoningProvider` uses (`generate`, `ready`) so it drops into `ChatReasoningProvider(local=…)` with no provider-side change. Frontend wiring reuses the existing `ModelConfig` (write-only key, `set_config`, `/api/model/config`) — the only additions are a `reasoning_client()` that branches on `backend`, a curated model list + its endpoint, and the Settings dropdown. Trust status needs no new code (ChatTurn already enforces it).

## Complexity Tracking

No constitution violations — section intentionally empty.
