# Implementation Plan: OpenRouter Provider with GLM as a Selectable Model

**Branch**: `020-openrouter-glm-provider` | **Date**: 2026-07-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/020-openrouter-glm-provider/spec.md`

## Summary

Add `OpenRouterClient` in `sr_agent/llm_core/` — a stdlib-only (urllib) client for OpenRouter's OpenAI-compatible `chat/completions` endpoint, duck-compatible with the two methods the reasoning provider uses (`generate(prompt, fmt=None, options=None) -> str`, `ready() -> bool`). Wire "openrouter" as a new connection method into the existing agent slots (`reasoning_client()` main, `additional_client()` additional, specs 018/019). The key is read from `OPENROUTER_API_KEY` (env), overridable per-process by the slot's write-only UI key. The UI gains OpenRouter as a method with a curated model dropdown led by the verified slug `z-ai/glm-5.2`. Output is `external_llm_output` by construction (via `ChatTurn`). No new package: OpenRouter is reached over plain HTTPS with stdlib. Optional/explicit/graceful — the core loop runs with no key and OpenRouter unused.

## Technical Context

**Language/Version**: Python 3.11 (backend) + Svelte/TS (UI).

**Primary Dependencies**: NONE new. `OpenRouterClient` uses `urllib` (stdlib), mirroring `LocalClient`. No `openai` SDK, no package added to `pyproject.toml`.

**Storage**: none. The key lives in the environment and/or the existing write-only in-process slot key.

**Testing**: pytest, offline/deterministic. The HTTP call is mocked (monkeypatch `urllib.request.urlopen` to return a fake OpenRouter JSON) — no real key, no network.

**Target Platform**: the operator frontend process + `sr_agent` llm_core.

**Project Type**: single project — one new kernel LLM client + slot wiring + a Svelte dropdown option.

**Performance Goals**: n/a (turn latency is the hosted model's).

**Constraints**: no new dependency (FR-007); key write-only, env-first; OpenRouter optional/explicit (never a silent fallback); `ready()` makes no paid/network call (key-present check only).

**Scale/Scope**: one new client (~90 lines), edits to `config.py`, `model_config.py`, `app.py` (model list), `Settings.svelte`, `api.ts`; ~3 test files; docs.

**Verified this session**: `z-ai/glm-5.2` is a real OpenRouter model ("Z.ai: GLM 5.2", 1M context). OpenRouter API: `POST https://openrouter.ai/api/v1/chat/completions`, `Authorization: Bearer <key>`, body `{model, messages:[{role,content}], response_format?}`, response `choices[0].message.content` (OpenAI-compatible; the `/models` endpoint fetched cleanly).

## Constitution Check

*GATE: evaluated against the 5 principles. Re-checked after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Secure-Kernel Trust Invariants** | ✅ PASS | OpenRouter output flows through `ChatTurn` → `external_llm_output` (structural, like Gemini/Claude); the `SourceType` ordering is unchanged. The key is a write-only secret (env-sourced or the existing write-only slot key): never returned, persisted, or logged. |
| **II. Human Authority** | ✅ PASS | A model backend only. No new privileged/irreversible action; the confirmation gate is untouched. |
| **III. Kernel / Pack Separation** | ✅ PASS | `OpenRouterClient` sits in `sr_agent/llm_core/` beside the other clients — kernel LLM client, no pack coupling. |
| **IV. Human-Gated Knowledge Promotion** | ✅ PASS | Unrelated to the knowledge loop. |
| **V. No Paid-API Dependency** | ✅ PASS | OpenRouter is paid → OPTIONAL (no key set → disabled; core runs on local/relay), EXPLICIT (operator selects the "openrouter" method — never a silent fallback), GRACEFUL (no key → clear disabled state), and adds **no new package** (stdlib HTTP). `ready()` performs no paid call. |

**Result: PASS — no violations. Complexity Tracking not required.**

## Project Structure

### Documentation (this feature)

```text
specs/020-openrouter-glm-provider/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/openrouter-provider.md
└── tasks.md   # /speckit-tasks
```

### Source Code (repository root)

```text
sr_agent/
├── llm_core/
│   └── openrouter_client.py   # NEW: OpenRouterClient (stdlib urllib), generate()/ready(), OPENROUTER_MODELS, OpenRouterUnavailable
└── config.py                  # EDIT: openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")

frontend/backend/
├── model_config.py            # EDIT: "openrouter" method in reasoning_client()/additional_client(); effective_openrouter_key(); backend allowed-sets += "openrouter"
└── app.py                     # EDIT: /api/model/models also returns the OpenRouter model list

frontend/ui/src/
├── panels/Settings.svelte     # EDIT: "OpenRouter (GLM)" method option in Main + Additional; GLM model dropdown when selected
└── lib/api.ts                 # EDIT: models endpoint type carries the openrouter list

tests/
├── unit/test_openrouter_client.py       # NEW: generate()/ready()/disabled + JSON mode, mocked HTTP
├── unit/test_model_config_openrouter.py  # NEW: "openrouter" builds OpenRouterClient; key precedence env/UI; None w/o key; key not in public()
└── architecture/test_openrouter_no_dep.py  # NEW: openrouter_client imports only stdlib+sr_agent (no new package; no `openai`/`requests`-SDK)

docs/roadmap.md  # EDIT: spec 020 landing entry
```

**Structure Decision**: Mirror spec 018 (Gemini) exactly, swapping the client. `OpenRouterClient` is a kernel LLM client, duck-compatible on `generate`/`ready`, so it drops into the slots with only a new `backend == "openrouter"` branch in `reasoning_client()`/`additional_client()`. Trust status needs no new code (ChatTurn). The stdlib-HTTP choice satisfies "no new package" (FR-007) and keeps Principle V clean.

## Complexity Tracking

No constitution violations — section intentionally empty.
