# Implementation Plan: Deterministic Compile-Fixers in the Drafting Loop

**Branch**: `032-deterministic-compile-fix` | **Date**: 2026-07-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/032-deterministic-compile-fix/spec.md`

## Summary

The drafting loop already runs deterministic code transforms (`_fix_import_paths`,
`_fix_nested_type_imports`) but relies on the MODEL to fix the two dominant MECHANICAL compile errors —
undeclared-identifier (×8) and address→interface (×3) — and the model does not converge. Add a
deterministic **error-driven repair step**: after a failed compile, apply a NEW `_fix_undeclared_import`
(auto-import a known symbol) and the existing `_fix_address_interface` (031's 9553 transform) to the
FAILING code, keyed on that compile's own forge output; if either changes the code, write + recompile
it (skip the model `fix()` for that round). No model call in the deterministic repair; idempotency
terminates it.

## Technical Context

**Language/Version**: Python 3.11+ (`scripts/`), Solidity 0.8.28 targets (forge).

**Primary Dependencies**: none new. Reuses `_path_for(file_map, name)` (name→real path), the
`symbol_index`, and the existing `_fix_address_interface` (spec 031).

**Storage**: N/A (in-process string transforms on the PoC source).

**Testing**: pytest, offline, deterministic. Model call + forge subprocess stubbed; SYNTHETIC fixtures
(invented names + synthetic forge errors); `test_no_target_material.py` guard.

**Target Platform**: the existing drafting/repair loop in `poc_queue_runner.py`.

**Project Type**: single-project CLI harness.

**Performance Goals**: a deterministic repair round is ONE incremental compile (~15s, measured) and
SAVES a model call (~46s) + often a whole attempt — net faster/cheaper, not slower.

**Constraints**: deterministic (no model call — Principle V); anti-invention (auto-import only a
KNOWN symbol); line/symbol-scoped (never touch an unflagged line); compile/pass verdict and the
exploit-logic path unchanged.

**Scale/Scope**: ~1 new `_fix_undeclared_import` transform, a bounded in-place deterministic-repair
sub-step (`DET_REPAIR_ROUNDS`) in the loop reusing it + `_fix_address_interface`, an event, tests. No
new files. The sub-step recompiles in-place and does NOT consume the `--attempts` budget (A1).

## Constitution Check

- **I. Trust Invariants** — PASS. Forge output is consumed as DATA to drive a mechanical rewrite of
  `external_llm_output` (the PoC); never promoted to instruction. Auto-import is gated on a name the
  index KNOWS is real (anti-invention) — it cannot import an attacker-suggested or invented name.
- **II. Human Authority** — PASS. Unchanged; a finding is still confirmed only by a passing PoC +
  falsification. No confirmation-gate change.
- **III. Kernel / Pack Separation** — PASS. Entirely in the audit harness (`scripts/`); no kernel/pack
  tool contract change.
- **IV. Human-Gated Knowledge** — N/A.
- **V. No Paid-API Dependency** — PASS, strengthened: the harness fixes more compile errors ITSELF
  (deterministic), REDUCING model round-trips. No new model dependency.

**Verdict**: no violations; no Complexity-Tracking entries.

## Project Structure

### Documentation (this feature)

```
specs/032-deterministic-compile-fix/
├── spec.md · plan.md · research.md · data-model.md
└── checklists/requirements.md
```

No `contracts/` — internal harness change, no external interface. Behavior pinned by offline tests.

### Source Code (repository root)

```
scripts/
  poc_queue_runner.py   # new _fix_undeclared_import(code, forge_output, symbol_index, file_map);
                        #   a deterministic error-driven repair step in the drafting loop that applies
                        #   it + the existing _fix_address_interface to the FAILING code and recompiles
                        #   before the model fix; a deterministic_fix log event.
tests/
  unit/test_poc_queue_runner.py           # _fix_undeclared_import (known/unknown/idempotent), the
                                          #   drafting-loop 9553 wiring; forge/model stubbed.
  integration/test_poc_runner_loop.py     # (if needed) the loop applies the deterministic fix + skips
                                          #   the model fix when it resolves the compile.
  architecture/test_no_target_material.py # unchanged guard.
```

**Structure Decision**: single-project CLI harness; change inside the existing drafting/repair loop +
one new pure transform helper in the same file. No new modules — consistent with specs 024–031.

## Approach (Phase 1 design)

1. **`_fix_undeclared_import(code, forge_output, symbol_index, file_map) -> (code, changed)`**: for
   each solc "Undeclared identifier `X`" / "Identifier not found `X`" in `forge_output`, if
   `_path_for(file_map, X)` resolves to a real path (X is a known top-level symbol), AND `X` is not
   already imported, prepend `import { X } from "<path>";`. Anti-invention: an X that `_path_for` does
   NOT resolve (typo/invention) is skipped. Ambiguous (index reports not-unique / `_path_for` empty) →
   skipped. Idempotent. Line-agnostic (adds an import at the top) — safe regardless of line drift.

2. **Deterministic error-driven repair — a bounded IN-PLACE sub-step** (`poc_queue_runner.py`, on the
   compiled-FALSE branch, before the model `fix()`): a `while` up to `DET_REPAIR_ROUNDS` (~2): apply
   `_fix_undeclared_import(code, blob, symbol_index, file_map)` and `_fix_address_interface(code, blob)`
   to the JUST-FAILED code (blob = its own `test.stdout+stderr`; line numbers valid — research
   Decision 2); if EITHER changed the code → log `deterministic_fix`, write the PoC, and RE-RUN
   `run_tests` (update `test`/`compiled`, IN-PLACE — this does NOT advance the `for attempt` counter, so
   it does not consume a model attempt — remediation A1/SC-008); if it now compiles → break out and let
   the attempt proceed as compiled; if a round makes NO change → break. After the sub-step: if compiled,
   proceed (real_pass/verdict as today); else, the model `fix()` runs as today (a fresh attempt).
   Bounded by `DET_REPAIR_ROUNDS` + idempotency (a second pass on the same error changes nothing) → it
   cannot loop.

3. **The existing error-AGNOSTIC post-fix pass** (`_fix_import_paths` + `_fix_nested_type_imports` at
   the draft ~L2491 and fix ~L2665 sites) is UNCHANGED — it still runs on the model's output. The new
   error-DRIVEN transforms are the separate step in (2).

### Edge handling
- No `[FAIL]`/error match, or `_path_for` doesn't resolve the name → no change → model fix as today
  (FR-003 anti-invention, FR-007 no-index no-op).
- `--no-symbol-index` / empty file_map → `_path_for` returns "" → `_fix_undeclared_import` no-op (FR-007).
- Semantic errors (6160/8936/2971/9582) → no transform matches → model + hints unchanged (FR-008).
- Compiled-but-failed (exploit-logic) attempt → the deterministic step is on the compile-FALSE branch
  only; the 029 trace-feedback path is untouched.

## Complexity Tracking

No constitution violations. One new pure helper + a small deterministic-repair branch (a `continue`
guarded by idempotent transforms) in the existing loop. No entries required.
