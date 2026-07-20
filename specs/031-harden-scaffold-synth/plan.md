# Implementation Plan: Harden Scaffold Synthesis with a Deterministic Repair Pass

**Branch**: `031-harden-scaffold-synth` | **Date**: 2026-07-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/031-harden-scaffold-synth/spec.md`

## Summary

`synthesize_scaffold` is one-shot: it writes the generated base, compiles a smoke test once, and on any
`no_build` deletes the base and returns None. Wrap the smoke build (poc_queue_runner.py ~L900–917) in a
**bounded deterministic repair loop**: on a non-compiling build, apply the harness's deterministic code
transforms to the base source (`_fix_import_paths` — already applied once — plus `_fix_nested_type_imports`
and a NEW `_fix_address_interface` for solc 9553), rewrite the base, and re-compile — up to a small fixed
number of rounds — accepting the moment it compiles. Add the 9553 address→interface rule ALSO to the
shared `_targeted_hints` (a text hint) so the drafting PoC benefits too. No model calls in the repair.

## Technical Context

**Language/Version**: Python 3.11+ (harness in `scripts/`), Solidity 0.8.28 targets (forge/Foundry).

**Primary Dependencies**: Foundry `forge test` in the sandbox (the smoke oracle); no new dependency.

**Storage**: N/A (in-place rewrite of the synthesized base file under the untracked audit area).

**Testing**: pytest, offline, deterministic. The smoke `run_tests` and the model call are stubbed;
SYNTHETIC fixtures only (invented contract/interface names — `test_no_target_material.py`).

**Target Platform**: the existing network-isolated `DockerSandbox` running `forge`.

**Project Type**: single-project CLI harness (`scripts/poc_queue_runner.py`).

**Performance Goals**: each repair round is one smoke build (same cost profile as today's single build),
bounded by the round count; error-driven fixes (9553) inherently need a compile to reveal them, so the
loop is necessary — the bound keeps worst-case cost at N× a smoke build only on findings that reach
synthesis (genuinely needed on this target). No added model calls.

**Constraints**: deterministic (no model call in the repair — Principle V unaffected); confined to
`synthesize_scaffold` + the shared hints; acceptance bar unchanged (trust only a compiling base);
untracked-area-only writes.

**Scale/Scope**: ~1 repair loop around the existing smoke build, ~1 new `_fix_address_interface`
transform, ~1 new `_targeted_hints` rule, a round-bound constant, events, tests. No new files.

## Constitution Check

*Gate evaluated against `.specify/memory/constitution.md`.*

- **I. Secure-Kernel Trust Invariants** — PASS. The repair operates on synthesized source (already
  `external_llm_output`) with deterministic transforms; forge output is consumed as DATA to drive a
  mechanical fix, never promoted to instruction/human_input. No new trust-boundary crossing.
- **II. Human Authority** — PASS. Unchanged. The scaffold is deploy infrastructure, compile-validated;
  a finding is still confirmed only by a passing PoC + falsification. No confirmation-gate change.
- **III. Kernel / Capability-Pack Separation** — PASS. The change is entirely in the audit harness
  (`scripts/`); no kernel/pack tool contract changes (it reuses `run_tests` unchanged).
- **IV. Human-Gated Knowledge Promotion** — N/A (no knowledge/lesson path change).
- **V. No Paid-API Dependency** — PASS, and strengthened: the repair is DETERMINISTIC (no model call),
  so synthesis becomes MORE reliable without adding any model dependency. A model-driven synth-fix loop
  is explicitly out of scope.

**Verdict**: no violations; no Complexity-Tracking entries.

## Project Structure

### Documentation (this feature)

```
specs/031-harden-scaffold-synth/
├── spec.md                # done
├── plan.md                # this file
├── research.md            # Phase 0 decisions
├── data-model.md          # repair-round / fixer entities
└── checklists/requirements.md   # done
```

No `contracts/` directory: internal harness change, no external interface. The behavioral contract is
pinned by the offline tests over synthetic fixtures.

### Source Code (repository root)

```
scripts/
  poc_queue_runner.py       # synthesize_scaffold: wrap the smoke build in a bounded repair loop;
                            #   new _fix_address_interface(code, forge_output) transform;
                            #   new 9553 rule in _targeted_hints; new events + round-bound constant.
tests/
  unit/test_poc_queue_runner.py   # repair-loop accept/reject + no-model + _fix_address_interface +
                                  #   _targeted_hints 9553 rule, over synthetic fixtures.
  architecture/test_no_target_material.py   # unchanged guard; fixtures stay synthetic.
```

**Structure Decision**: Single-project CLI harness; the change lives inside `synthesize_scaffold` and the
shared hint/transform helpers in the same file. No new modules — consistent with specs 024–030.

## Approach (Phase 1 design)

1. **Repair loop around the smoke build** (`synthesize_scaffold`): extract the existing smoke
   write+compile into a bounded loop. Per round: run the smoke `run_tests`; if `_compiled` → accept
   (emit `scaffold_synthesized`, return the path); else apply the deterministic transforms to the base
   `code` (see 2); if a transform CHANGED the code → rewrite `synth_path` (+ the smoke import is stable)
   and loop; if NO change (nothing left to fix deterministically) → stop and give up. Cap at
   `SYNTH_REPAIR_ROUNDS` (fixed, ~2–3). Infra exception → today's `infra` give-up (unchanged). On
   final give-up → `scaffold_synthesis_failed` `no_build` (unchanged), unlink the base.

2. **Deterministic transforms applied in the loop** (no model): `_fix_import_paths(code, project,
   base_dir=synth_dir)` (already used once), `_fix_nested_type_imports(code, symbol_index, file_map)`
   (existing), and a NEW `_fix_address_interface(code, forge_output)`. The first two are error-agnostic
   (safe to reapply, idempotent); the new one is error-DRIVEN — it reads the 9553 message.

3. **`_fix_address_interface(code, forge_output) -> (code, changed)`**: for each solc 9553 "Invalid
   implicit conversion from address to contract `<Type>`" the forge output reports, wrap the offending
   argument as `<Type>(address(x))`. Keyed off the real `<Type>` name and the pointed-at source line
   (line-by-line, mirroring `_fix_import_paths`' safety — touch only the flagged line, never others).
   Idempotent (a line already wrapped as `<Type>(...)` is left alone).

4. **`_targeted_hints` 9553 rule**: when the forge output contains the 9553 conversion error, append an
   authoritative hint — "pass `<Type>(address(x))` (or the typed variable), not a bare address". Specific
   (only when the error is present). Shared → benefits the drafting PoC (model-driven) as well as being
   the human-readable analogue of the deterministic transform.

5. **Events** (`synthesize_scaffold`): a per-round `scaffold_repair` event (round index + which
   transforms changed the code), then the existing `scaffold_synthesized` / `scaffold_synthesis_failed`.

### Edge handling
- First-build compiles → loop body runs once, accepts, zero repairs (FR-003 / SC-003 — unchanged).
- No deterministic change available → early stop, give up (FR-007 / edge "fixers make no change").
- Invented-API error (no 9553, no import fix applies) → no change → give up (FR-011 out of scope).
- Infra failure mid-loop → `infra` give-up, base discarded (unchanged).
- Acceptance bar: only a real `_compiled` smoke accepts — the loop never lowers it (FR-008).

## Complexity Tracking

No constitution violations; no added architectural complexity beyond one bounded loop + two small pure
helpers (one transform, one hint rule). No entries required.
