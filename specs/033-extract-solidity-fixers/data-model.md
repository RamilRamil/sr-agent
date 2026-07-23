# Data Model: Extract the Deterministic Solidity Compile-Fixer Layer

No persisted storage — this is a code-structure refactor. The "entities" are modules, functions, and
test kinds.

## Modules

- **`solidity_utils`** (new): shared low-level helpers `_tracked_sol`, `_SKIP_DIRS`, `_path_for`,
  `POC_SUBDIR` — imported by `poc_queue_runner.py` (grounding/index call sites) AND `solidity_fixers`.
  The cycle-breaker.
- **`solidity_fixers`** (new): the five deterministic transforms (`_fix_import_paths`,
  `_fix_nested_type_imports`, `_fix_address_interface`, `_fix_undeclared_import`, `_fix_setup_override`)
  + their private regexes + the five named sequence-functions. Imports `solidity_utils`.
- **`poc_queue_runner.py`** (existing): imports both; RE-EXPORTS the `_fix_*` (transitional); the two
  loops call the named sequence-functions. `_strip_comments` and `_targeted_hints` STAY here.

## Named sequence-functions (new — one per site, FR-012)

Each applies ONE site's exact current sequence + per-call args; NOT merged (merging is 034).
- synth pre-write: `import_paths(base_dir=synth_dir)`
- synth repair: `import_paths(base_dir=synth_dir) → nested → address`
- drafting in-place: `undeclared → address` (NOTE: no `import_paths` — pinned as an intentional gap)
- drafting post-model (draft) / (fix): `setup_override → import_paths(project) → nested`
Return `(code, applied: list[str])`; the loops emit the same `postfix_imports` / `scaffold_repair` /
`deterministic_fix` events as before.

## Test kinds

- **Characterization test** (`test_solidity_fixers.py`): pins each named function's output over a fixed
  fixture. The lasting guardrail.
- **Temporary differential test** (commit 1 only): asserts each named function == the inline output
  CAPTURED from the real loop (run through stub seams, read the written artifact); removed in commit 2.
- **Architecture test** (`test_fixer_sites.py`): asserts the named-function set BY NAME + that fixers are
  called only from inside them.

## Invariants

- Acyclic imports: `solidity_fixers` → `solidity_utils`; `pqr` → {both}. No `pqr` import inside the new
  modules (SC-009).
- Behavior byte-identical: every fixer and every named sequence produces the same output as before
  (characterization + existing tests).
- Events unchanged (name + shape).
- Re-exports transitional; internal callers use the modules directly; future patches target the module,
  not the pqr re-export.

## State transitions

None (pure refactor). The commit sequence (extract → swap → move-utils → move-fixers) is the only
"transition", each step green.
