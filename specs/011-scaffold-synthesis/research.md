# Research: Stage 1 Scaffold Synthesis

## R1 — Hook point: the existing insufficiency branch; swap the scaffold on success

**Decision**: Invoke synthesis from `_process_finding` immediately after the existing
`missing_types = scaffold_missing_types(...)` check (spec 009). When `missing_types` is
non-empty AND synthesis is enabled, call `synthesize_scaffold(...)`; on a validated
result, swap this finding's `scaffold`/`scaffold_paths`/`guard` to the synthesized base
BEFORE the draft loop runs (so the model inherits and imports the synthesized base).
On failure, keep the prior (insufficient) scaffold and log `scaffold_synthesis_failed`.
Gated by a new `--no-scaffold-synthesis` off-switch (default: ON — it fires only on
detected insufficiency and degrades safely, so on-by-default costs the common path
nothing).

**Rationale**: The insufficiency is already detected exactly here; acting on it in the
same place keeps the change localized and the common (sufficient) path completely
untouched (SC-003). Swapping the scaffold reuses every downstream mechanism unchanged
(the draft prompt already renders `scaffold` and tells the model to inherit it by its
import path), so a synthesized base is consumed identically to an operator-supplied
`--test-scaffold`.

**Alternatives considered**:
- *A separate pre-pass over all findings synthesizing scaffolds up front* — rejected:
  needs the per-finding grounding `_process_finding` already computes; inline is
  simpler and only does work when actually needed.
- *Default-off (opt-in)* — rejected: it only fires on detected insufficiency and always
  falls back honestly, so default-on maximizes the value with no common-path cost; the
  off-switch covers the honest-experiment framing.

## R2 — Synthesis is a one-shot generation, not the lookup round-trip

**Decision**: `synthesize_scaffold` prompts the harness's existing `client.generate`
(one shot) with a dedicated `SYNTH_SCAFFOLD_PROMPT`: the missing contract type(s)' real
source (via `read_location_source`/`SymbolIndex`), the existing auto-discovered scaffold
as a structural pattern, and the instruction to produce a Foundry abstract base that
inherits the existing base, declares the missing contract as a state variable, and
deploys/wires it in a setup helper. The output is stripped of markdown fences
(`_strip_fences`, existing).

**Rationale**: Scaffold synthesis is a single well-scoped generation, not an iterative
symbol-lookup, so the spec 007/008 `LOOKUP:`/tool-calling round-trip machinery is not
needed — a direct `generate` with strong grounding is simpler and sufficient. Reusing
the harness's own model (no new client) satisfies FR-002/constitution V; a more capable
model is reachable through the existing `--model`/`--host`.

**Alternatives considered**:
- *Route synthesis through the draft/fix lookup round-trip* — rejected: over-machinery
  for a one-shot base; the round-trip exists for a model iteratively resolving symbols
  mid-draft, not for producing one artifact.
- *Escalate to a relay/Claude for synthesis* — rejected: introduces a paid-API surface
  into the standalone harness (constitution V); the operator can already point a more
  capable model at `--model`/`--host` if desired.

## R3 — Validate by compiling a minimal inheriting smoke test; discard on non-compile

**Decision**: Write the synthesized base to an UNTRACKED audit area
(`audit/poc/_synth/<Name>.sol`), write a minimal smoke test that inherits it
(`contract _Smoke is <Name> { function test_compiles() public {} }`) into the
Foundry test dir, and run it via the existing `run_tests`. If `_compiled(...)` is True
on that run, the base builds → accept it (return its path). Otherwise discard it and
return None (`scaffold_synthesis_failed`, reason `no_build`). A model that returns no
usable base → reason `no_output`; an infra error during validation → reason `infra`.
Clean up the smoke test after.

**Rationale**: FR-004 sets the trust bar at COMPILE (not semantic perfection) — a base
that builds has resolvable imports, real types, and type-checking deploy code, which is
exactly what makes it usable for the model to inherit; a base that doesn't build would
fail every draft on the scaffold's own error and is strictly worse than the honest
fallback. This is the same generated-code-must-compile discipline specs 006/010 already
enforce, reusing the same sandbox. The untracked audit area satisfies FR-006 (tracked
source untouched); it's the harness's own generated infra, the same framing under which
`--test-scaffold` bases are accepted.

**Alternatives considered**:
- *Trust the synthesized base without compiling it* — rejected outright: the exact
  eval-robustness failure this project exists to avoid (trusting generated code on
  assertion).
- *Validate by a full deploy run (not just compile)* — rejected as the bar: a real
  deploy needs the setup-helper name the harness doesn't know; compile is the honest,
  achievable gate, and any resulting PASS is still mutation-verified (FR-008).

## R4 — Offline test seams

**Decision**: Two layers, mirroring spec 010. (a) `synthesize_scaffold` unit tests: a
fake `client` whose `.generate` returns scripted scaffold text + a monkeypatched
`pqr.run_tests` returning a scripted compile result — assert accept→path (compiles),
discard→None+event (won't compile / no output / infra), and that the synthesized file
lands only under the audit area (tracked source untouched, using `tmp_path`). (b) Loop
wiring: extend `tests/integration/test_poc_runner_loop.py`, monkeypatching
`pqr.synthesize_scaffold` to a scripted verdict (a path on success, None on failure) —
assert the finding's scaffold is swapped on success and left (with the fallback event)
on failure, and that synthesis is NOT consulted when the scaffold is already sufficient.

**Rationale**: Splitting "does synthesis produce+validate a base" (real audit-area
writes, scripted compile) from "does the loop swap or fall back" (scripted verdict)
keeps each test focused and fully offline (FR-007) — the exact unit-vs-integration
split specs 009/010 established, and it reuses their fake-model/fake-sandbox harness.

**Alternatives considered**:
- *Only integration tests* — rejected: the audit-area write + compile-validate logic
  deserves a direct test, not only a mock.
