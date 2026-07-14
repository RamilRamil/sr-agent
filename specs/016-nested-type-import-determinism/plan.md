# Implementation Plan: Nested-Type Import Determinism

**Branch**: `016-nested-type-import-determinism` | **Date**: 2026-07-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/016-nested-type-import-determinism/spec.md`

## Summary

Deterministically fix the nested-type named-import mistake that stalled H-01 six times, in
three index-driven layers (the knowledge loop surfaced the right lesson but the model didn't
obey it — verified live). A new mechanical guard `_fix_nested_type_imports` (mirroring
`_fix_setup_override`/`_fix_import_paths`) rewrites a named-import of a type the index knows
as nested (`Symbol.contract` non-empty) into `import { Container }` + `Container.Type`
references — model-independent, applied post-draft and every fix. The spec-015 grounding gains
the nested-reference note; `_targeted_hints` gains a `symbol_index` param + an authoritative
`Error 2904` rule. A tiny `SymbolIndex.nested_container(name)` helper encodes the
unambiguous-nested detection. All in `scripts/poc_queue_runner.py` + `scripts/solidity_index.py`;
offline-tested; no new dependency; no kernel-invariant or knowledge-loop change.

## Technical Context

**Language/Version**: Python 3.11+ (existing).

**Primary Dependencies**: none new. Reuses `scripts/solidity_index.py` (`SymbolIndex.lookup`,
`Symbol.contract`, the spec-015 `expand_referenced_types`), and the harness's existing
mechanical-guard pattern + `_path_for`/`_targeted_hints`/file-map in `scripts/poc_queue_runner.py`.

**Storage**: N/A.

**Testing**: pytest, offline. New `tests/unit` for the guard, the `nested_container` helper,
the grounding note, and the 2904 hint; the spec-009 fake harness confirms the guard runs at
draft+fix. No model, Docker, network (FR-007).

**Target Platform**: local dev; CI-safe.

**Project Type**: single project — a new mechanical guard + its two call sites, a note added
to `expand_referenced_types`, a `symbol_index` param + rule added to `_targeted_hints`, and a
`nested_container` helper on `SymbolIndex`.

**Performance Goals**: N/A (string processing + bounded index lookups).

**Constraints**: no false rewrites — only names the index unambiguously knows as nested
(FR-003); idempotent; the guard leaves library/remapped imports and unknown names alone; no
new dependency; no kernel-invariant / DATA-wrap / trust-hierarchy / promotion-gate / retrieval
change (FR-008).

**Scale/Scope**: one guard (~30 lines) + 2 call sites; one helper; one grounding note; one
hint rule; the offline tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Secure-Kernel Trust Invariants** — PASS. No change to DATA-wrapping, `SourceType`,
  memory HMAC, or the tool-call budget. The guard rewrites the model's *draft PoC* (which
  only ever runs inside the network-isolated sandbox) before compilation; the grounding note
  and hint inject *real target-derived* guidance. FR-008 pins this.
- **II. Human Authority** — PASS. No privileged/irreversible action.
- **III. Kernel / Capability-Pack Separation** — PASS. All changes are in the PoC harness
  (eval tooling) + its Solidity-index helper; no kernel/pack boundary touched.
- **IV. Human-Gated Knowledge Promotion** — PASS, and clarified. This feature ADDS
  deterministic repair *alongside* the knowledge loop; retrieval/promotion are unchanged
  (FR-008). It is, in fact, the evidence that for a mechanical index-detectable mistake,
  determinism should back up the suggestion-only loop.
- **V. No Paid-API Dependency** — PASS. Offline; no API; validation offline (FR-007).

No violations — **Complexity Tracking empty**. Constitution's "test-first for security-critical
behavior" applies as harness hardening (the no-false-rewrite guarantee and the guard's
idempotency are each written as a failing test first).

## Project Structure

### Documentation (this feature)

```text
specs/016-nested-type-import-determinism/
├── plan.md              # This file
├── research.md          # Phase 0 (R1–R5)
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1 (guard, helper, grounding note, hint)
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
scripts/solidity_index.py
└── SymbolIndex.nested_container(name) -> str | None
      # NEW: the container iff exactly one nested match and no top-level match; else None
      # (the unambiguous-nested detection all three layers use)

scripts/poc_queue_runner.py
├── _fix_nested_type_imports(code, symbol_index, file_map) -> (code, changed)   # NEW guard (US1)
├── _process_finding: apply the guard after draft AND after every fix           # (US1) + log postfix_nested_import
├── expand_referenced_types  (in solidity_index.py) → nested-reference note      # (US2)
└── _targeted_hints(forge_output, callable_api, file_map, code, symbol_index)    # (US3) + 2904 rule

tests/
├── unit/test_nested_import_guard.py     # rewrite / no-false-rewrite / mixed / idempotent (US1)
├── unit/test_nested_container.py        # the helper: nested vs top-level vs ambiguous
├── unit/test_struct_grounding.py (extend) # nested type → note; top-level → no note (US2)
└── unit/test_targeted_hints_2904.py     # nested → authoritative hint; unknown → none (US3)
```

**Structure Decision**: Single project. The core is one mechanical guard reusing the harness's
established `(code, changed)` post-generation pattern and the file-map import-path source,
gated by a small `SymbolIndex.nested_container` helper that encodes the strict determinism
boundary. US2/US3 are one-note and one-rule additions that reuse the same canonical
nested-type wording. Everything is offline-testable via `SymbolIndex.build_from_source`
fixtures and the spec-009 fake harness.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*

**Post-design re-check (after Phase 0/1)**: research.md's decisions (index-driven detection;
mirror the mechanical-guard pattern; strict ambiguity exclusion; one canonical wording across
grounding/hint/lookup) introduce no new violations — still PASS; the feature reinforces the
harness's determinism without touching any kernel invariant or the knowledge loop.
