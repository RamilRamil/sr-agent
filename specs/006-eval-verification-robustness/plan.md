# Implementation Plan: Eval/Verification Robustness for Generated-Artifact Success Gates

**Branch**: `006-eval-verification-robustness` | **Date**: 2026-07-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-eval-verification-robustness/spec.md`

## Summary

On 2026-07-05 the PoC-workability harness's compile-success detector (`_compiled()`)
was a **denylist** — it reported "compiled" whenever the `forge` transcript did not
contain a small fixed set of known failure phrases. A genuine compile failure worded
differently (`Error: Encountered invalid solc version ...`) slipped past it, producing
a false "all 3 findings compiled" milestone recorded in `docs/roadmap.md`. This plan:
(1) fixes and documents the general principle — **positive-signal detection**, not
denylist, for every automated verdict over a generated artifact, plus a **mandatory
cross-check** before any such verdict is recorded as a documented milestone; (2) audits
every existing verdict-producing check in `scripts/poc_queue_runner.py`
(`_compiled`, `_poc_defects`, `mechanism_signal`) against that principle, correcting or
explicitly justifying each; (3) produces a researched adopt/adapt/defer recommendation
on using SmartGraphical's call-graph analysis as a stronger mechanism-check than the
current regex-based `mechanism_signal`; (4) corrects the false milestone in
`docs/roadmap.md` and lands the principle in durable documentation.

No new service, no new dependency, no new runtime component — this is a correctness
fix + an audit + a documented decision, landed in the existing standalone harness
script and the existing docs tree.

## Technical Context

**Language/Version**: Python 3.11+ (matches the existing `sr_agent`/`scripts` codebase; no new language/runtime).

**Primary Dependencies**: None new. Uses the existing `sr_agent.tools.sandbox.DockerSandbox` /
`sr_agent.packs.audit.tools.write_execute.run_tests` plumbing already wired into
`scripts/poc_queue_runner.py`; the SmartGraphical research (User Story 3) reads
`sr_agent/packs/audit/tools/smartgraphical.py` and `specs/002-smartgraphical-integration/`
— it does not require installing the external SmartGraphical dependency to produce
a recommendation (see spec Assumptions).

**Storage**: N/A — no persistent state introduced. The harness's existing per-run JSONL
progress log (`_runner_progress.jsonl`) already carries an event per check; this feature
adds fields to those events (`compiled`, `mechanism`), not a new store.

**Testing**: `pytest` (project-standard). Every corrected/audited check gets a
know-good + a known-bad-with-an-unanticipated-message unit test (FR-008 / SC-005) —
mirroring the exact incident shape: a transcript representing genuine failure worded
differently than any check's hardcoded assumptions.

**Target Platform**: Same as the harness it audits — a developer/operator's machine
(or a Kaggle/Colab-hosted local model) driving `scripts/poc_queue_runner.py`
against Docker. No server, no UI.

**Project Type**: Internal engineering-quality feature (audit + correctness fix +
documentation) inside an existing single-repo CLI/tooling codebase. Not a new
project structure.

**Performance Goals**: N/A — this feature does not change the harness's runtime
performance characteristics; it changes what counts as "success."

**Constraints**:
- MUST NOT change the harness's other, already-working grounding levers (file map,
  callable_api, targeted repair, scaffold provisioning) — out of scope per spec.
- MUST NOT introduce new false negatives (a corrected check must still recognize a
  genuine success) — FR-008 / SC-005, tested explicitly.
- MUST NOT require the SmartGraphical external dependency to be installed in this
  environment to complete this feature — its User Story 3 deliverable is a
  documented recommendation, not a working integration (unless the recommendation
  itself is "adopt now" and a lightweight adoption is cheap — see research.md).

**Scale/Scope**: Small and bounded — one existing script
(`scripts/poc_queue_runner.py`, ~3 verdict-producing functions to audit), one Docker
image config already touched in this session (`docker/Dockerfile.foundry`,
already fixed — see research.md for why it's in scope as context, not new work),
and 2-3 documentation files (`docs/roadmap.md` correction; principle placement in
`docs/kernel.md` and/or `docs/audit-agent.md` and/or a new `docs/eval-principles.md`,
decided in Phase 1).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Applies? | Assessment |
|---|---|---|
| I. Secure-Kernel Trust Invariants | No kernel change | This feature touches only the standalone PoC-workability harness (`scripts/poc_queue_runner.py`), which already runs outside `orchestrator/loop.py`'s validate_action/confirmation path (a documented, deliberate simplification). No DATA-wrapping, SourceType, HMAC memory, or tool-call-budget code is touched. **PASS — not applicable.** |
| II. Human Authority for Privileged & Irreversible Actions | No new privileged action | Compile/execution checks are read-only classifications of a subprocess transcript; they do not perform or gate an irreversible action themselves (the harness's `run_tests` sandbox execution is unchanged by this feature). **PASS.** |
| III. Kernel / Capability-Pack Separation | No pack boundary change | The audited code lives entirely in `scripts/` (a standalone experiment), not in `sr_agent/orchestrator/` or `sr_agent/packs/`. SmartGraphical research reads the audit pack's existing tool (`sr_agent/packs/audit/tools/smartgraphical.py`) but proposes no kernel change. **PASS.** |
| IV. Human-Gated Knowledge Promotion | Related, reinforced | This feature is precisely about not letting an unverified automated signal become a trusted "fact" (a documented milestone) without independent corroboration — the same spirit as Principle IV applied to tooling verdicts instead of pipeline-steering knowledge. **PASS — reinforces intent.** |
| V. No Paid-API Dependency in the Core Path | Not applicable | No paid API is touched; SmartGraphical is a local, free structural-analysis engine, not a paid API. **PASS.** |

No violations. No Complexity Tracking entries required.

## Project Structure

### Documentation (this feature)

```text
specs/006-eval-verification-robustness/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (the audit-checklist "contract" + the
│                         #   SmartGraphical recommendation's decision record)
└── tasks.md             # Phase 2 output (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
scripts/
└── poc_queue_runner.py       # _compiled(), _poc_defects(), mechanism_signal() —
                               # audited/corrected per this feature (already
                               # partially corrected in this session; formalized
                               # + tested here)

tests/
└── unit/
    └── test_poc_runner_checks.py   # NEW — known-good / known-bad-unanticipated
                                     # cases per audited check (FR-008/SC-005)

docs/
├── roadmap.md                 # correct the false 2026-07-05 milestone entry
├── kernel.md / audit-agent.md # (or a new docs/eval-principles.md) — the general
│                               # principle + the SmartGraphical recommendation,
│                               # placement decided in Phase 1 data-model/quickstart
```

**Structure Decision**: Single-project layout (this repo already is one project —
`sr_agent/` + `scripts/` + `tests/` + `docs/`). No new top-level directory. The
feature's own artifacts live under `specs/006-eval-verification-robustness/`
per the existing spec-kit convention (matches 004/005); its actual deliverables
are a corrected script, a new unit test file, and doc corrections/additions in
the existing `docs/` tree — no new service or app boundary is introduced.

## Complexity Tracking

*No violations — table intentionally omitted.*
