# Implementation Plan: AST-Grounded, Agentic Lookup for PoC Drafting

**Branch**: `007-ast-grounded-poc-drafting` | **Date**: 2026-07-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-ast-grounded-poc-drafting/spec.md`

## Summary

The PoC-workability harness (`scripts/poc_queue_runner.py`) grounds the model's PoC
drafts with static, regex-extracted context blocks (file map, callable_api). This
session repeatedly hit the same shape of failure — the model invents a plausible
identifier because the real one wasn't in a static block we'd thought to extract
(interfaces → signatures → modifiers → struct fields, each fixed by one more one-off
regex). This plan replaces the regex extraction with a real Solidity AST parser
(`solidity-parser`, already feasibility-tested this session) behind a symbol-kind-agnostic
`SymbolIndex`, and adds a bounded, text-marker-based agentic lookup protocol to the
draft/fix loop so the model can request any symbol's real definition on demand —
closing the whole recurring pattern instead of adding a fifth regex. Existing static
grounding stays as a fast-start baseline (hybrid). Validated live against the
still-unsolved H-01 finding, with the outcome honestly recorded either way.

## Technical Context

**Language/Version**: Python 3.11+ (matches `scripts/poc_queue_runner.py`; no new runtime).

**Primary Dependencies**: `solidity-parser` (PyPI, ANTLR4-based; pulls in
`antlr4-python3-runtime` only) — feasibility-validated this session against the actual
target project (correctly parsed a real interface file's contracts, functions, and a
struct's full field list). This is a harness-only dependency (the standalone PoC
experiment), not a kernel/pack dependency; added to `scripts/` requirements, not
`sr_agent`'s core `pyproject.toml` dependency list (see research.md R5 for the exact
placement decision).

**Storage**: N/A — the `SymbolIndex` is built in-memory per run from parsing the
target project's `.sol` files; no persistence. Lookup activity is appended to the
harness's existing per-run JSONL log (`_runner_progress.jsonl`), same as every other
event.

**Testing**: `pytest`. Unit tests for `SymbolIndex` against real target fixtures
(struct-with-fields, function-with-modifiers, ambiguous-name cases per the spec's edge
cases); an offline test for the lookup-protocol detection/parsing logic (no model
needed); a live-run validation against H-01 per FR-007 (recorded, not asserted as
pass/fail in CI — this is an experiment, not a regression test).

**Target Platform**: Same as the harness itself — an operator's machine (or a
Kaggle/Colab-hosted local model over a tunnel) driving Docker.

**Project Type**: Internal engineering-capability feature inside an existing
single-repo CLI/tooling codebase (the standalone PoC-workability harness). Not a new
service or app boundary.

**Performance Goals**: N/A as a throughput target; the relevant constraint is
*latency/cost boundedness* per lookup budget (FR-004), not raw speed.

**Constraints**:
- MUST NOT require tearing out the existing static grounding blocks (file map,
  callable_api, scaffold, few-shot) — additive, hybrid (FR-005).
- MUST bound lookups per attempt (FR-004) — a fixed, small integer (research.md R2).
- MUST degrade gracefully if the target's source fails to parse (FR-009) — fall back
  to the existing static grounding for whatever couldn't be parsed, never abort the run.
- MUST NOT touch the kernel's `OrchestratorLoop`/ReAct tool-dispatch machinery (per
  spec Assumptions) — this is agentic behavior added to the standalone harness's own
  draft/fix loop only.
- MUST NOT require the SmartGraphical external dependency (a different tool, a
  different — already-decided — recommendation from spec 006).

**Scale/Scope**: Small and bounded — one new module (`solidity_index.py` or similar,
co-located with `scripts/poc_queue_runner.py`), changes to `draft()`/`fix()` and the
main attempt loop to support a bounded lookup round-trip, and reimplementing the
*existing* file-map/callable_api extraction on the same index is explicitly secondary
(spec Assumptions) — may be deferred past this feature's first cut if it risks
delaying the lookup capability itself.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Applies? | Assessment |
|---|---|---|
| I. Secure-Kernel Trust Invariants | No kernel change | Entirely within the standalone `scripts/poc_queue_runner.py`, which already runs outside `orchestrator/loop.py`'s validate_action/confirmation path (documented, deliberate). No DATA-wrapping/SourceType/HMAC/tool-budget code touched. **PASS — not applicable.** |
| II. Human Authority for Privileged & Irreversible Actions | No new privileged action | A symbol lookup is a pure, read-only, local parse-and-return operation on the target project's own already-committed source — it does not perform or gate an irreversible action. **PASS.** |
| III. Kernel / Capability-Pack Separation | No pack boundary change | `solidity-parser` and the new index/lookup code live entirely in `scripts/`, not `sr_agent/orchestrator/` or `sr_agent/packs/`. Per spec Assumptions, this is explicitly NOT wired into the kernel's ReAct loop. **PASS.** |
| IV. Human-Gated Knowledge Promotion | Not applicable | No pipeline-steering knowledge/memory is written by this feature; a lookup returns transient, in-memory, already-public target source facts for the current draft turn only. **PASS.** |
| V. No Paid-API Dependency in the Core Path | Not applicable | `solidity-parser` is a free, local, open-source PyPI package — not a paid API, and unrelated to the model backend. **PASS.** |

No violations. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/007-ast-grounded-poc-drafting/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (the lookup protocol contract; the
│                         #   SymbolIndex query contract)
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
scripts/
├── poc_queue_runner.py       # draft()/fix()/main loop extended with the bounded
│                             # lookup round-trip; existing static grounding kept
└── solidity_index.py         # NEW — SymbolIndex: parses the target project via
                               # solidity-parser, indexes contracts/interfaces/
                               # structs/enums/functions/modifiers by name, exposes
                               # lookup(name) -> real definition or "not found"

tests/
└── unit/
    └── test_solidity_index.py   # NEW — real target fixtures: struct-with-fields,
                                  # function-with-shared-modifiers (the exact
                                  # dedup-collision case from 006/this session),
                                  # ambiguous-name, not-found, unparseable-file
                                  # graceful-degradation

docs/
└── eval-principles.md   # cross-referenced (not modified) — FR-008's "report not
                          # found, never fabricate" is the same positive-signal
                          # doctrine spec 006 established
```

**Structure Decision**: Single-project layout (same repo as 006/the harness). No new
service or app boundary. The new `SymbolIndex` is a sibling module to
`poc_queue_runner.py` under `scripts/` (matching the harness's own standalone,
non-`sr_agent`-package status) rather than under `sr_agent/`, since it is specific to
the PoC-workability experiment, not a kernel or audit-pack capability.

## Complexity Tracking

*No violations — table intentionally omitted.*
