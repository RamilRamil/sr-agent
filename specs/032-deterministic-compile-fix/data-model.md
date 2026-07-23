# Data Model: Deterministic Compile-Fixers in the Drafting Loop

No persisted storage. In-process string values in the drafting loop. Listed for the contract the tests
pin.

## Entities

### PoC source (existing — `code`, a `str`)
The drafted/repaired PoC. The subject of the deterministic transforms; rewritten in place when a
transform changes it, then recompiled by the loop's next iteration.

### Undeclared identifier (from forge output)
A name a solc 7576/7920 error flags as undeclared/not-found. Auto-importable ONLY when
`_path_for(file_map, name)` resolves it to a real path (a known top-level project symbol). An
unresolved or ambiguous name is left for the model (anti-invention).

### `_fix_undeclared_import(code, forge_output, symbol_index, file_map) -> (code, changed)` (new)
Deterministic transform. For each 7576/7920-flagged name that `_path_for` resolves and that is not
already imported, prepend `import { name } from "<path>";`. Line-agnostic; idempotent; `changed=False`
(no-op) when nothing resolvable/undeclared is present or no file_map is available.

### `_fix_address_interface(code, forge_output) -> (code, changed)` (existing, spec 031)
The 9553 transform, now ALSO invoked in the drafting loop's deterministic repair step (was
synthesis-only). Line-number-keyed → applied to the FAILING code (valid line numbers), not the model's
rewrite.

### Deterministic-repair sub-step (new, in the loop — bounded, in-place)
On a compiled-FALSE branch, before the model `fix()`: a `while` up to `DET_REPAIR_ROUNDS` — apply both
transforms to `code` keyed on `test.stdout+test.stderr`; if either changed the code → log
`deterministic_fix`, write the PoC, and RE-RUN `run_tests` IN-PLACE (update `test`/`compiled`); accept
on compile, stop on no-change. Then proceed with the (possibly now-compiled) result; else model `fix()`.
- **Invariants**: no model call in the sub-step; it does NOT advance the `attempt` counter (does not
  consume the `--attempts` budget — A1); bounded by `DET_REPAIR_ROUNDS` + idempotency ⇒ cannot loop; a
  real recompile still decides the verdict; only the compile-FALSE branch is touched (exploit-logic path
  untouched).

### `DET_REPAIR_ROUNDS` (new module constant)
Fixed cap (~2) on the in-place deterministic-repair rounds per attempt. No CLI flag.

## Events (run-log records)

- **`deterministic_fix`** (new): `{finding_id, attempt, fixes: [names of transforms that changed the
  code]}` — the harness repaired a mechanical error itself (vs the model). Emitted only when a transform
  changed the code.
- **`postfix_imports`** (existing): the error-agnostic import pass — unchanged.

## State transitions

Per attempt: `write code → compile → (compiled? proceed : deterministic-repair? → continue :
model fix → post-fix pass → next attempt)`. Nothing persists across attempts beyond the existing
stall-detection signatures (untouched).
