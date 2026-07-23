# Data Model: Extract the Deterministic Solidity Compile-Fixer Layer

No persisted storage — this is a code-structure refactor. The "entities" are modules, functions, and
test kinds.

## Modules

- **`solidity_utils`** (new): shared low-level helpers `_tracked_sol`, `_SKIP_DIRS`, `_path_for`,
  `POC_SUBDIR`, **`_scaffold_base_name`** (T001) — imported by `poc_queue_runner.py` (grounding/index
  call sites) AND `solidity_fixers`. The cycle-breaker.
- **`solidity_fixers`** (new): the SIX deterministic transforms (`_fix_import_paths`,
  `_fix_nested_type_imports`, `_fix_address_interface`, `_fix_undeclared_import`, `_fix_setup_override`,
  **`_fix_scaffold_base`** — T001) + their private regexes + the named sequence-functions. Imports
  `solidity_utils`. NOTE `_ADDR_IFACE_RE` stays in pqr (used by `_targeted_hints`, not the fixer).
- **`poc_queue_runner.py`** (existing): imports both; RE-EXPORTS the `_fix_*` (transitional); the two
  loops call the named sequence-functions. `_strip_comments` and `_targeted_hints` STAY here.

## Named sequence-functions (new — one per site, FR-012)

Each applies ONE site's exact current sequence + per-call args; NOT merged (merging is 034). Each
returns `(code, applied: list[str])` — the ordered fixer-names that changed the code. The LOOPS keep
their own control flow + emit events from `applied` (byte-identical order/shape):
- `_seq_synth_prewrite(code, project, synth_dir)`: `import_paths(base_dir=synth_dir)` (caller discards)
- `_seq_synth_repair(code, forge_output, project, synth_dir, symbol_index)`:
  `import_paths(base_dir=synth_dir) → nested(symbol_index, NO file_map) → address` — loop uses `applied`
  for early-stop + `scaffold_repair_exhausted`
- `_seq_draft_inplace(code, forge_output, symbol_index, file_map)`: `undeclared → address` (NO
  `import_paths` — pinned intentional gap); loop logs `deterministic_fix{fixes=applied}`
- `_seq_postmodel(code, project, symbol_index, file_map, scaffold, guard)`:
  `setup_override(if guard) → import_paths(project) → nested(file_map) → scaffold_base` — shared by draft
  & fix; caller emits the FOUR per-fixer events (`postfix_setup`/`postfix_imports`/`postfix_nested_import`/
  `postfix_scaffold_base`) from `applied`, with its own `stage` ("draft" / `fix{attempt}`)

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
