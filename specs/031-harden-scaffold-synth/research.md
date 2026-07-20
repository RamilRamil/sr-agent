# Research: Harden Scaffold Synthesis

Phase 0 decisions.

## Evidence base

- **Live GLM-5.2 runs**: synthesis failed with solc 9553 `Invalid implicit conversion from address to
  contract IFoo` (the model wrote `someSetter(address(x))` for an interface-typed parameter). A
  DETERMINISTIC, mechanical error — the argument just needs wrapping as `IFoo(address(x))`.
- **Level-0 opportunity check (deterministic, no model)**: 0/5 findings on the eval target have an
  alternative existing base — synthesis is genuinely required (so spec 030 discovery ranking was
  deferred). Hardening synthesis is the measurable lever here.
- **Structural gap**: `synthesize_scaffold` is one-shot (compile once → discard on `no_build`), while
  the drafting loop gets N deterministic repair rounds. The asymmetry is the bug.

## Decision 1 — Deterministic repair loop, not a model-driven one

- **Decision**: On a non-compiling smoke build, apply the harness's deterministic CODE transforms and
  re-compile, up to a small fixed round bound; no model call in the repair.
- **Rationale**: The observed failures (9553, import depth) are mechanical — deterministic transforms
  fix them with zero model cost and zero nondeterminism. A model-driven fix loop would add a model call
  + a via_ir compile per round (expensive) and reintroduce variance. Constitution V stays clean (no new
  model dependency). Model-driven repair is explicitly out of scope.
- **Alternatives**: (a) model `fix()` per round — rejected (cost + variance); (b) raise the round bound
  to brute-force — rejected (bounded by what deterministic fixers can actually change; an early-stop on
  "no change" is the right terminator).

## Decision 2 — `_targeted_hints` gives HINTS; the synth repair needs TRANSFORMS

- **Decision**: The synth repair uses deterministic code TRANSFORMS (`_fix_import_paths`,
  `_fix_nested_type_imports`, new `_fix_address_interface`). The 9553 rule is ALSO added to
  `_targeted_hints` as a text hint, but that hint serves the drafting PoC (model-driven), not the
  no-model synth repair.
- **Rationale**: `_targeted_hints` returns advice for a MODEL to apply — useless in a no-model loop. The
  deterministic repair must mutate source itself, so 9553 needs a real transform (`_fix_address_interface`).
  Adding the hint too is cheap and shares the benefit with the PoC path (the spec's US2), but the two are
  distinct mechanisms and the plan keeps them separate.
- **Alternatives**: reuse only `_targeted_hints` in the synth loop — rejected (it produces no code
  change, so the loop would early-stop immediately with nothing fixed).

## Decision 3 — `_fix_address_interface` is line-scoped and error-driven

- **Decision**: Parse each solc 9553 "…from address to contract `<Type>`" occurrence (+ its pointed-at
  source line), and wrap the flagged argument as `<Type>(address(x))`, editing ONLY the flagged line
  (line-by-line, mirroring `_fix_import_paths`' safety). Idempotent — a line already wrapped is left alone.
- **Rationale**: The error names the exact type and location; a line-scoped rewrite is safe and precise,
  matching the existing deterministic-fixer discipline (never touch unflagged lines). Error-driven means
  it can only run AFTER a failing compile reveals the 9553 — which is why the loop (not a pre-compile
  pass) is required for it.
- **Alternatives**: a global address→interface heuristic without the error — rejected (would mis-wrap
  legitimate address arguments; the error is the authoritative signal).

## Decision 4 — Round bound + early stop

- **Decision**: `SYNTH_REPAIR_ROUNDS` fixed (~2–3). Stop early when a round produces NO code change
  (nothing left to fix deterministically). No operator flag.
- **Rationale**: Each round is a via_ir smoke build (~minutes), so the bound caps worst-case cost.
  Early-stop-on-no-change avoids a redundant recompile of identical source. 2–3 clears the realistic
  mechanical error stack (import depth + a couple of 9553s) without unbounded cost.
- **Alternatives**: unbounded until compile — rejected (cost); bound of 1 — rejected (that is today's
  one-shot behavior).

## Decision 5 — Acceptance bar unchanged (compile-only)

- **Decision**: A base is accepted the instant `_compiled(smoke)` is true; the repair loop never lowers
  the bar — it only grants more attempts to reach it.
- **Rationale**: Feature 011 FR-004's invariant (trust a synthesized base only if it actually compiles)
  is a correctness guard; the repair adds reach, not leniency.

## Testing approach (offline, deterministic)

- Stub the smoke `run_tests` with a scripted sequence (no_build → compiled) to drive the loop; stub the
  model (fail if the repair invokes it). SYNTHETIC fixtures: invented `IFoo`/`Foo` names, a captured-bad
  synth base, a synthetic 9553 forge error. No forge, no model, no target material.
- Unit: `_fix_address_interface` (wraps the flagged arg; idempotent; silent without 9553); the
  `_targeted_hints` 9553 rule (present with error, absent without); the repair loop (accept after a
  fixable round; reject after the bound; accept-on-first-build with zero rounds; no model call).
