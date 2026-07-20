# Data Model: Harden Scaffold Synthesis

No persisted storage. In-process values inside `synthesize_scaffold`. Listed for the contract the tests
pin.

## Entities

### Synthesized base source (existing — `code`, a `str`)
The model-generated abstract deploy-base, written to `synth_path` under the untracked audit area. Now
REWRITTEN in place across repair rounds as deterministic transforms change it. Never leaves the
untracked area; tracked source is untouched.

### Repair round (new — loop iteration)
One iteration of: run the smoke `run_tests` → if compiled, accept; else apply deterministic transforms;
if changed, rewrite + recompile; if unchanged, stop. Bounded by `SYNTH_REPAIR_ROUNDS`.
- **Invariants**: at most `SYNTH_REPAIR_ROUNDS` smoke builds; accept the instant a build compiles;
  give up on the first no-change round or after the bound; never a model call.

### Deterministic transform (existing + new)
A pure `code -> (code, changed)` rewrite applied in the loop:
- `_fix_import_paths(code, project, base_dir=synth_dir)` — import depth / SPDX (existing).
- `_fix_nested_type_imports(code, symbol_index, file_map)` — nested struct/enum imports (existing).
- **`_fix_address_interface(code, forge_output) -> (code, changed)`** (new) — wraps a 9553-flagged
  address argument as `<Type>(address(x))`, line-scoped, idempotent, silent when no 9553 present.

### 9553 hint rule (new, in `_targeted_hints`)
When forge output contains "Invalid implicit conversion from address to contract `<Type>`", append an
authoritative hint naming `<Type>` and prescribing `<Type>(address(x))`. Text guidance for the
model-driven drafting PoC (NOT used by the no-model synth repair). Specific — emitted only on the error.

## Configuration

- **`SYNTH_REPAIR_ROUNDS`** (new module constant): fixed bound (~2–3) on repair rounds. No CLI flag.

## Events (run-log records)

- **`scaffold_repair`** (new): per round — the round index and which transforms changed the code.
- **`scaffold_synthesized`** (existing): accept — the base compiled (possibly after repair).
- **`scaffold_synthesis_failed`** (existing): give-up — `no_build` after the bound, or `infra`/`no_output`
  as today. Reason vocabulary unchanged.

## State transitions

Within one `synthesize_scaffold` call: `generated → [smoke build → (compiled? accept : transform →
changed? rewrite+loop : give-up)]×≤N`. Nothing persists across calls.
