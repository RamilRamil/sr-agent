# Implementation Plan: Run the Report→PoC Batch on a Hosted Model

**Branch**: `022-poc-harness-hosted-model` | **Date**: 2026-07-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/022-poc-harness-hosted-model/spec.md`

## Summary

Add a `--provider {local|openrouter|gemini}` option to `scripts/poc_queue_runner.py` so the existing report→PoC batch machinery can be driven by a capable hosted model (GLM via OpenRouter, or Gemini) instead of only the local Ollama model. The change is a thin seam: a client factory, a hosted-aware startup gate (skip Ollama-only `warm()`/`available()`/keep-alive; use `ready()` = key present), forcing the marker protocol for hosted (no tool-calling), and widening the `client: LocalClient` annotations to the shared `generate`-duck union. All drafting/fixing/grounding/gate/verify logic is reused verbatim — only the model changes. Default stays `local` with byte-identical behavior.

## Technical Context

**Language/Version**: Python 3.11 (harness).

**Primary Dependencies**: none new. Reuses `OpenRouterClient` (spec 020, stdlib) and `GeminiClient` (spec 018, optional `google-genai` extra). Both share `generate(prompt, fmt=None, options=None) -> str` / `ready()` with `LocalClient`.

**Storage**: none. Hosted key from env (`OPENROUTER_API_KEY` / `GEMINI_API_KEY`); never persisted/logged/argv.

**Testing**: pytest, offline/deterministic — a fake `generate`-client and monkeypatched env; the client factory, protocol resolution, and readiness gate are extracted into small pure functions that test without a real model, network, or container. The heavy live end-to-end (real GLM + Docker + forge) is an operator run, not automated.

**Target Platform**: developer/operator CLI (`scripts/poc_queue_runner.py`).

**Project Type**: single project — a `scripts/` harness change only.

**Performance Goals**: n/a (per-finding latency is the model's).

**Constraints**: hosted is opt-in (`--provider`); default `local` unchanged; hosted uses the marker protocol only (no tool-calling); key never in argv/log/result; a "compiled + gate PASS" remains a mechanical reproduction (existing `_poc_defects` structural gate + vacuous-pass guard untouched); target/report/PoCs stay outside the agent repo (existing behavior).

**Verified this session**: marker path calls only `client.generate` (`_select_protocol` returns for "marker" without `supports_tools()`); the three clients' `generate` signatures match; the startup block (`main`, ~2335) builds `LocalClient` then does keep-alive `available()` + `warm()` + `ready()`.

## Constitution Check

*GATE: evaluated against the 5 principles. Re-checked after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Secure-Kernel Trust Invariants** | ✅ PASS | Hosted model output is untrusted external LLM output, exactly as local/relay output. A compiling PoC + passing check remains a mechanical reproduction, NEVER a safety verdict — the existing `_poc_defects` structural gate and the vacuous-pass guard are unchanged. No trust-hierarchy change. |
| **II. Human Authority** | ✅ PASS | PoC writing/execution stays sandbox-isolated as today; no confirmation-gate change. The harness is an operator-run batch; the model only drafts. |
| **III. Kernel / Pack Separation** | ✅ PASS | Change is confined to the `scripts/` harness — no kernel or pack change. |
| **IV. Human-Gated Knowledge Promotion** | ✅ PASS | Unrelated to the knowledge loop. |
| **V. No Paid-API Dependency** | ✅ PASS | Hosted providers are OPT-IN via `--provider`; the default stays `local` and the harness runs with no hosted component present. OpenRouter adds no package; Gemini uses the existing optional extra and errors clearly if absent. No paid API is ever required for the harness to function. |

**Result: PASS — no violations. Complexity Tracking not required.**

## Project Structure

### Documentation (this feature)

```text
specs/022-poc-harness-hosted-model/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/poc-harness-provider.md
└── tasks.md   # /speckit-tasks
```

### Source Code (repository root)

```text
scripts/
└── poc_queue_runner.py   # EDIT:
    #  - import OpenRouterClient/OPENROUTER_MODELS, GeminiClient, gemini SIMPLE_MODELS
    #  - `--provider {local|openrouter|gemini}` (default local)
    #  - build_generation_client(provider, model, host, timeout) -> client   (factory, pure)
    #  - resolve_lookup_protocol(provider, requested) -> "marker"|"tool"      (hosted → force marker; tool+hosted → error)
    #  - hosted_ready_error(provider, client, model) -> str|None              (no key / missing SDK message, no network)
    #  - main(): build client via factory; for hosted skip keep-alive/warm/available and gate on ready() via hosted_ready_error; local path unchanged
    #  - widen `client: LocalClient` → `LocalClient | OpenRouterClient | GeminiClient` on the marker/draft/fix functions

tests/
└── unit/test_poc_harness_provider.py   # NEW: factory builds the right client; hosted forces marker + rejects tool; ready-gate no-key/missing-SDK message; local path unchanged; mocked generate returns through the client

docs/roadmap.md · RUN_FRONTEND.local.md  # EDIT: how to run the batch on GLM/Gemini (env key, --provider … --lookup-protocol marker); CLI path (frontend trigger later)
```

**Structure Decision**: Extract three small pure helpers (`build_generation_client`, `resolve_lookup_protocol`, `hosted_ready_error`) so the provider/protocol/readiness logic is unit-testable offline without invoking `main()` or a real model. `main()` calls them; the local branch is byte-identical to today. The draft/fix/verify machinery is untouched — only the client object and the startup gate differ. Annotations widen to the existing `generate`-duck union (no new class/Protocol needed; `from __future__ import annotations` makes them non-evaluated strings).

## Complexity Tracking

No constitution violations — section intentionally empty.
