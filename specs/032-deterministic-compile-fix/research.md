# Research: Deterministic Compile-Fixers in the Drafting Loop

Phase 0 decisions.

## Evidence base (measured, eval-first)

Compile-error frequency across live GLM-5.2 + deepseek-v3.2 runs over strata findings 1 & 2 (≤8
attempts): **undeclared-identifier (solc 7576/7920) = 8** (dominant), **address→interface (9553) = 3**,
wrong-arg-count (6160) = 3, invalid-token (8936) = 2, cannot-instantiate-interface (2971) = 1. finding-2,
on a SUFFICIENT scaffold, compiled only 2/8 — the loop does not converge because it relies on the model
to apply mechanical fixes. The two dominant classes ARE mechanical → fix them deterministically.

## Decision 1 — Which error classes are in scope

- **Decision**: In scope = undeclared-identifier (auto-import) + address→interface (reuse 031's
  transform). Out = wrong-arg-count, invalid-token, cannot-instantiate-interface, member-not-found.
- **Rationale**: the two chosen are MECHANICAL — a deterministic rewrite exists (add the real import;
  wrap the arg in the real type). The others are SEMANTIC: wrong-arg-count needs the real arguments;
  invalid-token is broken syntax; cannot-instantiate-interface needs the concrete impl; member-not-found
  already has a hint. No safe deterministic rewrite → leave to the model + existing `_targeted_hints`.
- **Alternatives**: try to fix wrong-arg-count from `callable_api` — rejected (choosing/ordering args
  is semantic, high false-fix risk).

## Decision 2 — Apply error-driven transforms to the FAILING code, before the model fix (not after)

- **Decision**: Apply `_fix_undeclared_import` and `_fix_address_interface` to the just-failed `code`,
  keyed on THAT compile's forge output, BEFORE calling the model `fix()`; if either changes the code,
  recompile it deterministically (via the loop's next iteration) and skip the model fix that round.
- **Rationale**: `_fix_address_interface` is LINE-NUMBER-keyed (it locates the flagged argument by the
  error's `file:line`). The model `fix()` rewrites the whole PoC, so the OLD error's line number would
  point at the wrong line in the NEW code — a line-drift mis-edit. Applying the transform to the code
  that PRODUCED the error keeps the line numbers valid. It also SAVES a model call when a deterministic
  fix alone resolves the compile — faster + cheaper (measured: ~15s recompile vs ~46s model call), and
  directly attacks the non-convergence (the harness fixes mechanically instead of re-prompting).
- **Alternatives**: put both in the existing post-fix pass (after `fix()`) — rejected for
  `_fix_address_interface` (line drift). `_fix_undeclared_import` alone is line-agnostic and would be
  safe there, but a single uniform placement (both before the model fix) is cleaner and higher-value.

## Decision 3 — Anti-invention gate via `_path_for`/the index

- **Decision**: Auto-import `X` ONLY when `_path_for(file_map, X)` resolves to a real path (X is a known
  top-level project symbol). An unresolved name (typo/invention) or an ambiguous one is left for the
  model/hint — never speculatively imported.
- **Rationale**: The project's core discipline is no-invented-API. A speculative import for an invented
  name would MASK the real problem (the model hallucinated) and could add a new error. `_path_for` is
  the existing, trusted name→path resolver (it powers the current import-fix and member rules), so the
  gate reuses ground truth, not a new heuristic.
- **Alternatives**: `symbol_index.lookup(X)` — equivalent known-symbol signal, but `_path_for` also
  yields the path in one call; use it. A fuzzy/nearest-name import — rejected (invents).

## Decision 4 — Idempotency terminates the deterministic step

- **Decision**: Both transforms are idempotent (a name already imported is not re-added; a 9553 line
  already wrapped is left alone). So the deterministic-repair `continue` cannot loop forever — a second
  pass on the same error produces no change and falls through to the model fix.
- **Rationale**: mirrors 031's synth-repair early-stop-on-no-change; the no-change condition is the
  natural terminator, and idempotency guarantees it.

## Testing approach (offline, deterministic)

- SYNTHETIC fixtures: invented contract/interface names + synthetic forge 7576/7920/9553 errors + a
  stubbed `file_map`/index that resolves the KNOWN names and not the unknown ones. No forge, no model,
  no target material.
- Unit: `_fix_undeclared_import` (adds import for a known name; no-op for unknown — anti-invention;
  idempotent; no-op with empty file_map); the drafting-loop 9553 wiring (a compile-FALSE attempt whose
  forge output has a 9553 gets the wrapped call and a `deterministic_fix` event). Integration (if
  needed): the loop applies the deterministic fix and skips the model fix when it resolves the compile.
