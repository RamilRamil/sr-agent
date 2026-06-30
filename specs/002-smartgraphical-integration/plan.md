# Implementation Plan: SmartGraphical Integration

**Branch**: `002-smartgraphical-integration` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-smartgraphical-integration/spec.md`

## Summary

Add SmartGraphical as a third deterministic analysis engine in SR-agent, complementary to
Slither (syntactic) and Mythril (symbolic). SmartGraphical contributes (a) logic-level findings
and (b) an accurate per-function read/write + call graph. The engine is invoked **as an external
tool producing JSON** (subprocess CLI `sg_cli.py … json`, or the `smartgraphical:local` Docker
image), mirroring the existing Slither integration — keeping SR-agent's dependency surface clean
and the engine swappable, even though the SmartGraphical code is the user's own. Output is parsed
and mapped onto the existing `Finding` model (tool_output provenance) and the `sig.py` interference
graph. All findings remain hypotheses, gated on PoC verification.

Approach is phased by user story: **US1** (findings engine, MVP) → **US2** (graph→SIG) →
**US3** (hypothesis-invariant assertions). Each phase is independently testable and shippable.

## Technical Context

**Language/Version**: Python 3.11+ (SR-agent), invoking SmartGraphical (Python 3.10+) as a subprocess.

**Primary Dependencies**: existing SR-agent stack (pydantic, click); SmartGraphical invoked via
its CLI / Docker image — no new Python package dependency added to SR-agent.

**Storage**: existing HMAC-signed JSONL episodic memory (findings written as `tool_output`).

**Testing**: pytest. Pure mapping/graph logic unit-tested on fixture JSON (no SmartGraphical
needed); a live integration test auto-skips when SmartGraphical/Docker is unavailable (same
pattern as `test_slither_live.py`).

**Target Platform**: local CLI (darwin/linux), Docker for sandboxed engines.

**Project Type**: single project — CLI security tool (`sr_agent/` package).

**Performance Goals**: SmartGraphical pass adds seconds per file (regex parser is fast); must not
block the audit when unavailable (auto-skip).

**Constraints**: offline-capable (no paid API); engine output consumed as data and wrapped through
existing guardrails; findings never auto-confirmed.

**Scale/Scope**: per-audit a handful to dozens of Solidity files; one new tool adapter + one SIG
builder + report attribution. No redesign of memory, guardrails, Stage 3, or PoC paths.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The repository constitution is an unfilled template, so the gate is evaluated against SR-agent's
**de-facto architectural invariants** (the security thesis the whole project enforces):

| Invariant | This feature complies? |
|---|---|
| **Orchestration Plane is the boundary; tool output is untrusted data** | ✅ SmartGraphical output is parsed, wrapped, sanitized, stored as `tool_output` — never executed. |
| **Findings are hypotheses, not truth (confirmed only by PoC)** | ✅ Ingested findings carry unconfirmed status; PoC remains the only path to confirmation (US3). |
| **Determinism for analysis/planning; LLM only where needed** | ✅ Engine + graph + mapping are fully deterministic; no LLM added. |
| **Append-only, HMAC-signed memory; provenance enforced** | ✅ Reuses `episodic.write` with `source_type=tool_output`; no new write path or status authority. |
| **Pragmatic-parsing, best-effort, fail-safe** | ✅ Auto-skip when unavailable; never aborts the audit. |
| **No paid-API dependency** | ✅ SmartGraphical is local/free. |

**Result: PASS** — no violations, Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-smartgraphical-integration/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions (invocation, mappings, graph→SIG)
├── data-model.md        # Phase 1 — SmartGraphical Finding/Graph entities + mapping
├── quickstart.md        # Phase 1 — running an audit with the SmartGraphical engine
├── contracts/
│   └── smartgraphical-tool.md   # the consumed JSON contract + internal function signatures
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
sr_agent/
├── tools/
│   ├── static_analysis.py        # EXTEND: run_smartgraphical() + parsers (alongside run_slither)
│   └── smartgraphical.py          # NEW: SG invocation + JSON→Finding + JSON→graph mapping
├── planner/
│   ├── sig.py                     # EXTEND: build_sig_from_smartgraphical() (graph→SIG seam)
│   └── stage3.py                  # (unchanged contract; consumes whichever SIG is provided)
├── orchestrator/
│   └── pipeline.py                # EXTEND: static pass also runs SmartGraphical; SIG source select
├── io/
│   └── report.py                  # EXTEND: per-finding engine attribution
└── models/
    └── finding.py                 # (reused; maybe add an "engine" provenance field on payload)

tests/
├── unit/
│   ├── test_smartgraphical.py     # NEW: JSON→Finding + JSON→graph mapping (fixture, no SG)
│   └── test_sig.py                # EXTEND: SIG-from-SG-graph cases
├── integration/
│   └── test_smartgraphical_live.py# NEW: live SG run, auto-skip if unavailable
└── fixtures/
    └── smartgraphical/            # NEW: sample SG JSON outputs + a small inheritance contract
```

**Structure Decision**: Single-project CLI tool. The integration lands as one new module
(`tools/smartgraphical.py`) plus extensions to the existing static-analysis pass, SIG builder,
pipeline, and report — reusing every existing seam (Finding, tool_output, sig.py, Stage 3, PoC).

## Complexity Tracking

> No constitution violations — section intentionally empty.
