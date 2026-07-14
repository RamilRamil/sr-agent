# Research: Live-Run Harness Robustness

Phase 0. Grounded in the actual code and a direct probe against the live target. One
hypothesis from the spec (US2) was corrected here (R2) — the fix changed accordingly.

## R1 — Extract the Solidity span; fail a no-code reply; tool→marker fallback

**Decision**: Replace `_strip_fences` with a `_extract_solidity(text)` that (a) if a fenced
block is present, takes its contents; (b) then trims to the span from the first real
Solidity token (`// SPDX`, `pragma`, `import`, `contract`, `interface`, `library`,
`abstract contract`) through the last line that is plausibly code, dropping leading/trailing
prose; (c) returns `""` when no Solidity token is found. Callers in `draft()`/`fix()` and
`_generate_with_lookups`/`_generate_with_tool_calls` use it; when it returns `""`, the
draft/fix is treated as failed (no PoC written). In the tool path specifically, an empty
extraction triggers a one-shot fallback to the marker protocol for that finding.

**Rationale**: `_strip_fences` only strips a fence when the reply *starts* with ```` ``` ````
(observed: qwen3-coder:30b prepends "Looking at the compilation errors… Let me analyze…"
prose → the whole thing lands in `H_01.t.sol` → `Error (2314): Expected ';'` at line 1; and
in tool mode the reply was code-free → a 0-byte `.sol` → "No tests found" vacuous pass).
Anchoring on the first Solidity token is robust to arbitrary prose and to markdown, and the
"no token ⇒ failed draft" rule kills the empty/prose file at the source. Bonus: it also
stops a prose-corrupted PoC from polluting the *next* run's `SymbolIndex` build (see R4).

**Alternatives considered**:
- *Only strip a leading prose paragraph* — rejected: brittle; the model interleaves prose
  and multiple fenced blocks. Span-from-first-Solidity-token is deterministic.
- *Keep writing the file and let forge reject it* — rejected: that is exactly today's
  failure (wasted attempts, false vacuous pass).

## R2 — CORRECTION: fields are already returned on lookup; ground them PROACTIVELY instead

**Decision**: The spec's original US2 ("the lookup response doesn't include struct fields")
is **wrong** — verified by a direct probe: `SymbolIndex.lookup("TExitUpperBounds")` on the
live target returns `definition = "struct TExitUpperBounds { uint32 p0; uint32 p1;
TExitParams r0; TExitParams r1; TExitParams r2; }"` and `_render_lookup_response` already
emits it. The real gap is **timing**: the model constructs the struct on attempt 1 (guessing
`maxFeePpm, maxLockSeconds, minLockSeconds`) and only looks it up on attempt 4, after it has
already stalled. The fix is therefore to **proactively expand** the field lists of
struct/enum types referenced by the finding's `callable_api` into the draft grounding (one
level of nesting, so `TExitParams` inside `TExitUpperBounds` is also shown), leaving the
on-demand lookup untouched.

**Rationale**: Surfacing the fields where the model first constructs the type (the draft
prompt) removes the guess entirely, rather than relying on the model to self-correct via a
lookup it doesn't perform in time. The definitions already exist in the `SymbolIndex` — this
is routing existing data into the grounding, no new parsing. Nesting one level covers the
observed case (opaque `p0/p1` + nested `TExitParams`).

**Alternatives considered**:
- *Change the lookup response* (original US2) — rejected: it already returns fields; would
  fix nothing.
- *Prompt the model to "look up structs before constructing"* — rejected: weaker (depends on
  the model complying) than just handing it the fields up front.
- *Expand every struct in the project* — rejected: prompt bloat; scope to types the
  `callable_api` actually references, budget-bounded.

## R3 — Capture only on a genuinely-better verdict, not any signature change

**Decision**: Tighten `_maybe_capture_lesson` (spec 014): capture a candidate only when the
current attempt reached a **better verdict** (`compiled` or `real_pass`) AND the previous
attempt was stuck on a non-empty signature now cleared — never on a lateral move to a
different error or a regression. Concretely, pass the current `compiled`/`real_pass` flags
into the capture check and require compile-success; drop the "prev signature absent ⇒
resolved" heuristic as the sole trigger.

**Rationale**: The current heuristic ("prev error-signature not in current") fires on a
*regression* too: attempt 5 regressed into prose-in-`.sol` → a new `Expected ';'` error →
the two real errors "disappeared" → a false lesson (`1de2c917`) pairing the real signature
with garbage prose as the "fix". Requiring real compile progress makes capture mean "a fix
that actually cleared a stuck error", which is the only kind of lesson worth a human's
review. (Once R1 lands, the prose regression itself largely stops — but the trigger must be
correct regardless.)

**Alternatives considered**:
- *Post-filter bad candidates at review* — rejected: the human gate already quarantines
  them, but manufacturing junk wastes reviewer attention and erodes trust; fix the trigger.
- *Require `real_pass` only* — rejected: too strict; a previously-uncompilable signature that
  now `compiled` is genuine progress worth capturing.

## R4 — Parser noise is downstream of R1 + a known unsupported syntax (out of scope)

**Decision**: The `symbol_index_built unparsed_files: 4` noise has two sources: (a) the
prose-corrupted PoC in `audit/poc/` being parsed as Solidity (fixed transitively by R1,
which stops writing prose), and (b) the target's newer `mapping(address token => …)`
named-key syntax that `solidity-parser` doesn't support. (b) is pre-existing, affects only a
few files, and is **out of scope** here (the index degrades gracefully per file). Note it;
don't fix it in this feature.

**Rationale**: R1 removes the self-inflicted half; the parser-version half is a separate,
larger concern (upgrade/replace the parser) not driven by these three findings.

## R5 — Validation is fully offline

**Decision**: All three stories are exercised with the spec-009 fake-model/fake-sandbox
harness: US1 via scripted replies (prose-prefixed, prose-only, tool-empty) asserting the
written PoC / failed-draft / marker-fallback; US2 via a `SymbolIndex` over a fixture with a
nested struct asserting the grounding contains the expanded fields; US3 via scripted
verdict/signature transitions (stuck→compiled ⇒ 1 capture; stuck→different-error ⇒ 0). No
model, Docker, network, or paid API; no new dependency.

**Rationale**: The offline harness and the SymbolIndex fixtures already exist; these are
ordinary additions to the existing test tiers.
