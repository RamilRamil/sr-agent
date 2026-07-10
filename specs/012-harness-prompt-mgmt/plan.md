# Implementation Plan: Harness Prompt Management

**Branch**: `012-harness-prompt-mgmt` | **Date**: 2026-07-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/012-harness-prompt-mgmt/spec.md`

## Summary

Bring the PoC-harness prompts under the same versioned prompt-management the kernel
already uses: fetch each via `tracer.get_prompt_versioned(name, fallback=<constant>)`
(the constant is the byte-exact fallback → tracing-off runs are identical), record the
prompt name+version in each draft/fix generation's trace metadata, and add a best-effort
seeding step (production, v1). Additive only — the existing `get_prompt` and its kernel
callers are untouched; Langfuse stays optional (fallback anchor). All offline-testable.

## Technical Context

**Language/Version**: Python 3.11+ (existing `scripts/`/`sr_agent/` codebase).

**Primary Dependencies**: none new. Reuses the already-deployed Langfuse Prompt
Management + `sr_agent/eval/tracer.py` `Tracer` (spec 001 T079), and the harness's
existing `Tracer` wiring into draft/fix (spec 009). The `langfuse` SDK is already a dep.

**Storage**: N/A — prompt versions live in Langfuse (self-hosted, optional); the
hardcoded constants remain the offline default.

**Testing**: pytest, offline. A fake/disabled tracer returns the fallback constant
(identical-behavior test); a fake tracer returning a versioned prompt exercises the
fetch + version-in-metadata path; a fake Langfuse client exercises the seeding
create-calls. All through the spec-009 fake-model harness — no Langfuse/Ollama/Docker/
network (FR-008).

**Target Platform**: local dev machine; CI-safe for the offline suite.

**Project Type**: single project — a small additive method on `sr_agent/eval/tracer.py`
plus prompt-routing + provenance in `scripts/poc_queue_runner.py` and its tests.

**Performance Goals**: one extra (cached, best-effort) prompt fetch per generation when
tracing is on; zero cost when off (immediate fallback). No hot-path concern.

**Constraints**: byte-identical prompts when tracing off (FR-002); additive `Tracer`
change, `get_prompt` unchanged (FR-004); Langfuse never a hard dependency (FR-006,
constitution V); a format-failure on an edited prompt falls back, never crashes (FR-007).

**Scale/Scope**: `Tracer.get_prompt_versioned` (additive); a `_resolve_prompt` helper +
routing the six harness prompts through it; threading `tracer` into `extract_tasks` and
`synthesize_scaffold` (which don't have it yet); recording prompt provenance in the
draft/fix generation metadata; a `seed_prompts` step; offline tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Secure-Kernel Trust Invariants** — PASS. The only kernel-adjacent change is an
  ADDITIVE method on the shared `Tracer` (an observability utility, not the secure
  orchestrator); `get_prompt`'s contract and every kernel caller are unchanged. A
  Langfuse-fetched prompt is `external` config whose trust anchor is the hardcoded
  fallback constant (used on any fetch/format failure, FR-007) — the harness never
  hard-depends on remote prompt text. No `SourceType`/memory/tool-budget change.
- **II. Human Authority for Privileged & Irreversible Actions** — PASS. No new
  privileged/irreversible action; prompt fetch is read-only best-effort, seeding is a
  best-effort write to the self-hosted Langfuse.
- **III. Kernel / Capability-Pack Separation** — PASS. No pack boundary touched.
- **IV. Human-Gated Knowledge Promotion** — PASS. Prompt versions are observability
  config, not steering knowledge promoted from tool output; editing a prompt in Langfuse
  is an explicit human act (the operator), matching the kernel's own T079 model.
- **V. No Paid-API Dependency** — PASS. Langfuse is self-hosted + optional; the harness
  runs unchanged without it via the fallback constants (FR-006).

No violations — Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/012-harness-prompt-mgmt/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (get_prompt_versioned + provenance)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
sr_agent/eval/
└── tracer.py             # + get_prompt_versioned(name, fallback) -> (text, version|None)
                          #   ADDITIVE — get_prompt unchanged (FR-004)

scripts/
└── poc_queue_runner.py   # + _resolve_prompt(tracer, name, fallback) -> (text, {name,version})
                          #   with a format-failure fallback to the constant (FR-007)
                          # + route the 6 prompts (poc-extract/draft/fix/exploit-checklist/
                          #   lookup-marker/synth-scaffold) through it; thread `tracer`
                          #   into extract_tasks + synthesize_scaffold (which lack it)
                          # + record prompt provenance (name+version list) in the draft/
                          #   fix generation metadata (via _traced_round_trip)
                          # + seed_prompts(tracer/client) — best-effort push, no-op when
                          #   Langfuse disabled; invoked once at run start (guarded)

tests/unit/
└── test_local_client.py OR test_poc_queue_runner.py  # get_prompt_versioned +
                                # _resolve_prompt (fallback / versioned / format-failure)
tests/integration/
└── test_poc_runner_loop.py    # EXTEND: tracing-off → identical fallback prompt;
                                # fake versioned tracer → version recorded in metadata
```

**Structure Decision**: Single project. One additive `Tracer` method (kernel-adjacent
shared util), the rest confined to the standalone harness + tests. Prompt routing goes
through one `_resolve_prompt` helper so the format-failure fallback (FR-007) and
provenance capture live in one place. Threading `tracer` into `extract_tasks` and
`synthesize_scaffold` is the only signature change (both are called from sites that
already hold the tracer). Tests reuse the spec-009 fake harness.

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*

**Post-design re-check (after Phase 0/1)**: research.md's decisions (additive
`get_prompt_versioned`; a single `_resolve_prompt` helper with format-fallback; thread
tracer into the two prompt-consuming functions that lack it; provenance in generation
metadata; guarded best-effort seeding) introduce no new violations — still PASS on all
five principles.
