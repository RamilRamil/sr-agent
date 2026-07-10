# Implementation Plan: Stage 1 Scaffold Synthesis

**Branch**: `011-scaffold-synthesis` | **Date**: 2026-07-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/011-scaffold-synthesis/spec.md`

## Summary

Close the loop spec 009 opened: when `scaffold_missing_types` detects that a finding's
auto-discovered scaffold cannot deploy a contract the finding needs, synthesize a
deploy-base that declares+deploys it (via the harness's own model, grounded in the
missing contract's real source + the existing base as pattern), COMPILE-validate it in
the sandbox, and — only if it builds — use it for that finding's draft/fix loop.
On any failure, log `scaffold_synthesis_failed` and fall back honestly to the prior
insufficient-scaffold behavior. Any resulting PASS still goes through spec 010's
mutation-verify. All orchestration offline-testable; no kernel change; no new
dependency.

## Technical Context

**Language/Version**: Python 3.11+ (existing `scripts/`/`tests/` codebase).

**Primary Dependencies**: none new. Synthesis uses the harness's existing `LocalClient`
(same `--model`/`--host`); validation reuses `run_tests`/`DockerSandbox` +
`_compiled` (spec 009-tested). Grounding reuses `SymbolIndex`/`read_location_source`
and `read_scaffold` (existing).

**Storage**: a synthesized base written to an UNTRACKED audit area under the target
project (e.g. `audit/poc/_synth/`), never touching git-tracked source (FR-006). The
harness already writes PoCs under `audit/poc/`.

**Testing**: pytest, offline. `synthesize_scaffold` is unit-tested with a fake client
(scripted scaffold text) + monkeypatched `run_tests` (scripted compile result). The
loop wiring is tested in spec-009's `tests/integration/test_poc_runner_loop.py` by
monkeypatching `pqr.synthesize_scaffold` to a scripted verdict (same pattern spec 010
used for `mutation_verify`). No Ollama/Docker/network (FR-007). Live H-01 optional.

**Target Platform**: local dev machine; CI-safe for the offline suite.

**Project Type**: single project — extends `scripts/poc_queue_runner.py` (a
`synthesize_scaffold` step wired into `_process_finding` after the
`scaffold_missing_types` check) and the spec-009 test harness.

**Performance Goals**: synthesis fires ONLY on detected insufficiency (rare) and adds
one model call + one deploy-only compile; the common (sufficient-scaffold) path is
untouched (FR-001/SC-003).

**Constraints**: MUST use the harness's existing model, no paid-API dependency
(FR-002, constitution V); MUST compile-validate before use, discard non-compiling
(FR-004); MUST fall back honestly, never block (FR-005); MUST NOT modify tracked source
(FR-006); any PASS still mutation-verified (FR-008). No bug-bounty target code in tests.

**Scale/Scope**: one `SYNTH_SCAFFOLD_PROMPT`, one `synthesize_scaffold(...)` function
(generate → write to audit area → compile-validate → return path/text or None), the
loop wiring, a `--no-scaffold-synthesis` off-switch, and offline tests for
synthesize/validate/use/fallback.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Secure-Kernel Trust Invariants** — PASS. Entirely within the standalone harness.
  A synthesized scaffold is generated code that is (a) written only to an untracked
  audit area and (b) executed only inside the existing network-isolated,
  capability-dropped sandbox for compile-validation — same discipline as every PoC the
  harness already runs. Model output is never trusted on assertion; it's gated on a
  real compile (eval-robustness doctrine). No kernel control-flow/SourceType/memory
  touched.
- **II. Human Authority for Privileged & Irreversible Actions** — PASS. No new
  privileged/irreversible action; synthesis writes an ephemeral test base and compiles
  it. Findings remain hypotheses; a synthesized-scaffold PASS is still gated by spec
  010's mutation-verify (FR-008), so nothing is auto-promoted.
- **III. Kernel / Capability-Pack Separation** — PASS. No pack boundary touched.
- **IV. Human-Gated Knowledge Promotion** — PASS. No knowledge writes; the synthesized
  base is per-finding generated infra, not steering knowledge.
- **V. No Paid-API Dependency** — PASS. Synthesis uses the harness's existing
  local/tunnel model (FR-002); offline tests by requirement (FR-007).

No violations — Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/011-scaffold-synthesis/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (synthesize_scaffold contract)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
scripts/
└── poc_queue_runner.py   # + SYNTH_SCAFFOLD_PROMPT
                          # + synthesize_scaffold(project, task, missing_types,
                          #     existing_scaffold, symbol_index, client, sandbox, log,
                          #     *, image, fork_rpc) -> Path | None
                          #     (generate a deploy-base → write to audit/_synth →
                          #      compile-validate via a deploy-only smoke test →
                          #      return the file path, or None on any failure)
                          # + wire into _process_finding right after the
                          #     scaffold_missing_types check: on success, swap the
                          #     finding's scaffold/scaffold_paths/guard to the
                          #     synthesized base; on failure, log + keep the prior path.
                          # + --no-scaffold-synthesis off-switch (default: on, since it
                          #     only fires on detected insufficiency and degrades safely)

tests/unit/
└── test_poc_queue_runner.py   # synthesize_scaffold unit tests (validate-pass → path;
                                #   validate-fail/no-output/infra → None + event)

tests/integration/
└── test_poc_runner_loop.py    # EXTEND: loop wiring — insufficient scaffold →
                                #   synthesize (monkeypatched verdict) → used vs fallback
```

**Structure Decision**: Single project, extending the spec-009/010 surface.
`synthesize_scaffold` is a self-contained function (generate → write → validate) reusing
existing grounding (`SymbolIndex`/`read_location_source`/`read_scaffold`) and the
existing sandbox `run_tests`/`_compiled`. It is invoked only from `_process_finding`'s
existing insufficiency branch, so the common path is untouched. Tests follow spec 010's
split: unit-test the function directly (real audit-area writes to `tmp_path`, scripted
compile), loop-test the wiring via a monkeypatched `synthesize_scaffold` verdict.

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*

**Post-design re-check (after Phase 0/1)**: research.md's decisions (one-shot generate
+ audit-area write + compile-validate; hook only into the existing insufficiency
branch; default-on with an off-switch) introduce no new violations — still PASS on all
five principles.
