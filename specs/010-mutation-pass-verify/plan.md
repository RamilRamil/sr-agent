# Implementation Plan: Mutation-Based PASS Verification

**Branch**: `010-mutation-pass-verify` | **Date**: 2026-07-06 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/010-mutation-pass-verify/spec.md`

## Summary

Turn a `forge` PASS into a verifiable claim: when a PoC reaches a genuine PASS,
re-run it against an ephemeral copy of the target source with the finding's own fix
applied. If the PoC now FAILS, the exploit genuinely depends on the vulnerability →
verified pass. If it STILL PASSES, the PoC wasn't testing the bug → downgrade to
`unverified_pass`. When no machine-applicable fix exists or the diff won't apply,
degrade honestly to `mutation_verify_unavailable` and keep `passed` — never fabricate
a failure. All orchestration offline-testable through spec 009's fake harness; no
kernel change.

## Technical Context

**Language/Version**: Python 3.11+ (existing `scripts/`/`tests/` codebase).

**Primary Dependencies**: none new. Diff application uses standard `git apply`
(fallback `patch`) via the existing subprocess surface; the patched re-run reuses the
existing `run_tests`/`DockerSandbox` path. `_compiled` (spec 009-tested) judges whether
the patched source built.

**Storage**: N/A beyond an ephemeral temp copy of the target source, deleted after the
verify run; the real target tree is never modified (FR-004).

**Testing**: pytest, offline. The apply/extract logic is tested against a real tmp
"project" + a real small unified diff (fast, deterministic). The two sandbox runs
(vulnerable — already done by the loop; patched — the new one) are driven by the spec
009 monkeypatched `run_tests` (scripted `TestResult` per run). No Ollama/Docker/network
(FR-008). A live H-01 confirmation is optional (US3), not the completion bar.

**Target Platform**: local dev machine; CI-safe for the offline suite.

**Project Type**: single project — extends `scripts/poc_queue_runner.py` (fix
extraction + a `mutation_verify` step wired into `_process_finding`'s `real_pass`
branch) and the spec-009 test harness.

**Performance Goals**: mutation-verify runs ONLY on a genuine PASS (rare, expensive by
nature), so a full ephemeral source copy + one extra sandbox run is acceptable; it
never touches the common non-passing paths (FR-007).

**Constraints**: MUST NOT modify the real target tree (FR-004); MUST NOT downgrade on
an inability to verify (FR-005) or an infra error (FR-006); MUST use standard patch
tooling, no fuzzy patching (FR-009); MUST run only post-hoc on an already-passing PoC
(FR-007). No bug-bounty target code embedded in tests (synthetic fixtures only).

**Scale/Scope**: fix extraction (deterministic, from report text), a `mutation_verify`
function (copy → apply → re-run → classify), one new outcome (`unverified_pass`) + the
`mutation_verify_*` events, wired into `_process_finding`; offline tests for each path.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Secure-Kernel Trust Invariants** — PASS. Entirely within the standalone harness
  and its tests. The patched re-run reuses the SAME network-isolated, capability-dropped
  Docker sandbox against a copy of already-present source — no new execution surface,
  no new privilege, and the fix diff is applied by deterministic tooling, never
  executed as an instruction. Strengthening a success verdict is squarely the
  eval-robustness doctrine (docs/eval-principles.md), not a weakening of any invariant.
- **II. Human Authority for Privileged & Irreversible Actions** — PASS. No new
  privileged/irreversible action; mutation-verify is a read-only-in-effect verifier on
  an ephemeral copy (the real tree is untouched, FR-004). Findings remain hypotheses;
  this makes a *confirmed* PoC's confirmation stronger, never auto-promoting anything.
- **III. Kernel / Capability-Pack Separation** — PASS. No pack boundary touched.
- **IV. Human-Gated Knowledge Promotion** — PASS. No knowledge writes; the verify
  verdict is a run-log event, not steering knowledge.
- **V. No Paid-API Dependency** — PASS. No API; the patched re-run is the same local
  sandbox path; offline tests by requirement (FR-008).

No violations — Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```text
specs/010-mutation-pass-verify/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (mutation_verify contract)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
scripts/
└── poc_queue_runner.py   # + extract_fix_for_finding(report, finding) — deterministic
                          #   diff pull from the report section (NOT via the model, to
                          #   avoid mangling the diff); the finding gains a `fix` field.
                          # + mutation_verify(project, task, poc_rel, sandbox, log, ...)
                          #   — ephemeral copytree → git-apply the fix → re-run the SAME
                          #   PoC via run_tests → classify verified/unverified/unavailable.
                          # + wire into _process_finding's real_pass branch: a surviving
                          #   pass downgrades outcome to `unverified_pass`.

tests/unit/
└── test_poc_queue_runner.py   # fix-extraction + diff-apply + classify unit tests

tests/integration/
└── test_poc_runner_loop.py    # EXTEND (spec 009): mutation-verify loop scenarios —
                                #   verified / unverified_pass / unavailable — via the
                                #   scripted fake sandbox (patched-run result scripted)
```

**Structure Decision**: Single project, extending the spec-009 surface. Fix extraction
is deterministic report parsing (keeps the model out of the diff). `mutation_verify`
reuses `run_tests`/`_compiled`; it is invoked only from `_process_finding`'s existing
`real_pass` branch, so the common paths are untouched. Tests extend the spec-009
fake-model + fake-sandbox harness — the patched re-run is just one more scripted
`run_tests` result.

## Complexity Tracking

*No Constitution Check violations — this section is intentionally empty.*

**Post-design re-check (after Phase 0/1)**: research.md's decisions (deterministic fix
extraction; ephemeral copytree + `git apply` with a `patch` fallback; hook only into
the `real_pass` branch) introduce no new violations — still PASS on all five
principles.
