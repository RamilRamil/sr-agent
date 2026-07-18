# Implementation Plan: Make via_ir Compilation Viable in the Harness Sandbox

**Branch**: `027-sandbox-viair-memory` | **Date**: 2026-07-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/027-sandbox-viair-memory/spec.md`

## Summary

Spec 026's first live run couldn't compile the target at all — `solc SIGKILL` (OOM). Diagnosed from
the artifact, triangulated three ways: the sandbox caps memory at `512m`, the target builds with
`via_ir` (needs GBs), and a clean-dir re-run gave 2/2 SIGKILL. A cold via_ir build doesn't fit in
512m. Fix, two parts:

1. **Memory (correctness):** the STANDALONE harness constructs its sandbox with an env-tunable,
   calibrated ceiling (`SR_SANDBOX_MEMORY`, generous default) — applied ONLY there. The kernel
   `DockerSandbox` class default and both secure-agent sites stay at 512m. No kernel change (the
   `memory_limit` field already exists).
2. **Cache reuse (cost):** the falsification copy stops excluding `cache_forge`/`out`, so a passing
   proof's patched rebuild is incremental (seconds, small memory peak) instead of a cold full build —
   the most frequent cold-build site.

Grounded in [research.md](research.md). Scoping + copy change are guarded by offline tests; the memory
value is confirmed by a LIVE calibration step (offline tests can't run a heavy build).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: none new — stdlib `os`/`shutil`; Docker via the existing sandbox

**Storage**: N/A

**Testing**: pytest, offline for the scoping + copy change; the memory-sufficiency calibration is a
live operator step (a heavy container build), explicitly not a unit test

**Target Platform**: operator CLI (`scripts/poc_queue_runner.py`) + the shared sandbox

**Project Type**: single project — a scoped change to operator tooling; NO kernel/pack behavior change

**Performance Goals**: turn a passing proof's falsification from a multi-minute full via_ir rebuild
into a seconds-long incremental one; let a cold full build survive instead of being killed

**Constraints**: no security invariant may change (FR-009); the harness rise must not leak into the
secure agent (FR-003); the memory default must be empirically confirmed (FR-004)

**Scale/Scope**: ~3 changed lines in `scripts/poc_queue_runner.py` (a factory + the copy skip list),
one new architecture test, one unit assertion, plus a quickstart pre-step. No `sr_agent/` change.

## Constitution Check

| Principle | Status | Rationale |
|---|---|---|
| **I. Secure-Kernel Trust Invariants** | ✅ PASS | No trust promotion, no new source type. The sandbox still executes attacker-influenced PoC code under the SAME isolation; only its memory ceiling (a DoS knob) rises, and only for the operator harness. |
| **II. Human Authority** | ✅ PASS | No privileged/irreversible action. Findings are still confirmed only by a verified PoC — this fixes the compile step that was being OOM-killed, changing nothing about what counts as verified. |
| **III. Kernel / Pack Separation** | ✅ PASS | The change is in `scripts/` operator tooling. The kernel `DockerSandbox` class is UNCHANGED (memory_limit was already a field); no kernel or pack code is edited, no new kernel→pack import. |
| **IV. Human-Gated Knowledge Promotion** | ✅ PASS | No knowledge-store writes. |
| **V. No Paid-API Dependency** | ✅ PASS | No model involved; stdlib only. |

**Security invariants explicitly preserved (FR-009):** `--network none`/opt-in-bridge-for-fork,
`--cap-drop ALL`, `--security-opt no-new-privileges`, `--pids-limit`, ephemeral `--rm`, and
"PoCs execute ONLY inside the sandbox" (`tests/architecture/test_harness_sandbox_only.py`, still
green). Memory is DoS-protection, not isolation. **Gate result: PASS on all five; Complexity Tracking
empty.**

## Project Structure

### Documentation (this feature)

```
specs/027-sandbox-viair-memory/
├── spec.md              # what & why (3 stories; security is first-class)
├── plan.md              # this file
├── research.md          # 5 decisions, grounded in code + the SIGKILL artifact
├── quickstart.md        # the warm-cache pre-step + how to set SR_SANDBOX_MEMORY + calibration
├── tasks.md             # (/speckit-tasks)
└── checklists/
    └── requirements.md
```

No `data-model.md`/`contracts/` — a config knob + a copy-skip change, exercised through the CLI.

### Source Code (repository root)

```
scripts/
└── poc_queue_runner.py                # MODIFIED (~3 lines)
    ├── _harness_sandbox()             #   NEW: DockerSandbox(memory_limit=env SR_SANDBOX_MEMORY | default)
    ├── main() @ ~2668                 #   use _harness_sandbox() instead of bare DockerSandbox()
    └── _MUTVERIFY_COPY_SKIP @ ~1682   #   drop "out"/"cache_forge"; keep ".git"/"node_modules"

tests/architecture/
└── test_harness_sandbox_memory.py     # NEW — harness raised, secure agent not (FR-003/FR-010)

tests/unit/
└── test_poc_queue_runner.py           # EXTENDED — _MUTVERIFY_COPY_SKIP no longer skips the cache (FR-005)
```

**Structure Decision**: the entire code change lives in `scripts/poc_queue_runner.py` (the operator
harness) — the kernel sandbox and the secure agent are untouched, which is the whole point of the
scoping. The new guard test goes in `tests/architecture/` beside `test_harness_sandbox_only.py` and
`test_verification_no_model.py` (the established home for these invariant guards).

## Design

### US1/US3 — the scoped memory raise

`_harness_sandbox()` reads `SR_SANDBOX_MEMORY` (default `"6g"` — generous headroom above the killed
512m; via_ir on this mid-size target peaks in the low-GB range) and returns
`DockerSandbox(memory_limit=<that>)`. `main()`'s `sandbox = DockerSandbox()` becomes
`sandbox = _harness_sandbox()`. Nothing else changes; the same instance already flows to both
`run_tests` and `mutation_verify`, so both get the raised ceiling.

The guard test (`test_harness_sandbox_memory.py`) asserts, deterministically and offline:
- `_harness_sandbox().memory_limit` parses to **strictly more than** `DockerSandbox().memory_limit`
  (the kernel default, still `"512m"`) — a tiny `_mem_bytes("6g")` parser in the test;
- via AST, `pipeline.py` and `loop.py` construct `DockerSandbox()` with **no** `memory_limit` kwarg —
  the secure agent is not raised (FR-003).

Flipping the harness back to bare `DockerSandbox()`, or adding a `memory_limit` to a secure-agent
site, fails this test (FR-010/SC-005).

### US2 — cache in the falsification copy

`_MUTVERIFY_COPY_SKIP` becomes `shutil.ignore_patterns(".git", "node_modules")` (drop `"out"`,
`"cache_forge"`). `mutation_verify`'s `copytree` then carries the forge cache; `_git_apply` changes
the fix's file; forge's content-keyed cache recompiles only that file + dependents. Everything else in
`mutation_verify` is unchanged — ephemeral copy, same PoC re-run, `rmtree` in `finally`, real tree
never touched (FR-006/FR-007). A unit assertion pins the new skip set.

### US-warm — the first build

Minimal, lowest-risk form (research Decision 4): document a one-time host-side `forge build` warm-up
in quickstart before a run/batch, so the mounted project's cache is warm and only the first build is
cold. (An automated warm-up call in `main()` is noted as an optional refinement, not required for the
correctness fix, since Decision 1 already makes a cold build survive.)

## Test Strategy

**Offline, deterministic** (`tests/architecture/test_harness_sandbox_memory.py` +
`tests/unit/test_poc_queue_runner.py`):

- `_harness_sandbox().memory_limit` > kernel default (parsed to bytes); default applies when
  `SR_SANDBOX_MEMORY` unset; a set env value is honored (monkeypatch).
- AST: `pipeline.py`/`loop.py` do not pass `memory_limit` (secure agent unraised).
- `DockerSandbox().memory_limit == "512m"` (kernel default unchanged).
- `_MUTVERIFY_COPY_SKIP` excludes `.git`/`node_modules` and NOT `cache_forge`/`out`.
- The existing `test_harness_sandbox_only.py` still passes (no isolation change).

**Live calibration** (operator step, not a unit test — FR-012/SC-001/SC-007): a cold via_ir build of
the reference target at `512m` (expect SIGKILL) vs the default (expect success); then re-run the
finding that gave 2/2 SIGKILL and confirm it reaches the compiled stage. Documented in quickstart and
run once by the operator.

## Complexity Tracking

None. The Constitution Check passes on every principle with no deviation to justify.
