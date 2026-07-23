# Research: Extract the Deterministic Solidity Compile-Fixer Layer

Phase 0 decisions. This is a refactor, so the "research" is the dependency inventory + the technique
choices that make each risky step safe.

## Decision 1 — Module boundary (from the FR-011 dependency inventory)

- **Decision**: `solidity_utils` = the shared low-level helpers the fixers pull in that are ALSO used by
  non-fixer code (`_tracked_sol`, `_SKIP_DIRS`, `_path_for`, `POC_SUBDIR`). `solidity_fixers` = the five
  `_fix_*` + their private regexes + the five named sequence-functions. `poc_queue_runner.py` imports
  both and re-exports the `_fix_*`.
- **Rationale**: fixers → utils, pqr → {utils, fixers} is acyclic. Leaving the shared helpers in pqr and
  importing them into the fixer module would make the fixer module import pqr while pqr re-exports the
  fixers — a cycle. A third utils module is the standard break.
- **Refinement found**: `_strip_comments` is used by `_poc_defects`/grounding/scaffold but by NO fixer,
  so it does NOT move — `_poc_defects` is not touched AT ALL (tighter than FR-007's "import-only touch"
  allowance). The spec's tentative list is narrowed by the actual inventory.
- **Alternatives**: (a) shared helpers into the fixer module → drags grounding/index call sites (not a
  fixer move); (b) leave in pqr + import → cycle. Both rejected.

## Decision 2 — The differential test CAPTURES the inline output; never transcribes it (FR-014)

- **Decision**: the commit-1 differential test obtains the inline side by RUNNING the real loop
  (`synthesize_scaffold` / `_process_finding`) through the existing stub seams and READING the artifact
  it writes (`synth_path.write_text` / `write_poc`), then asserts byte-equality with the extracted named
  function on the same inputs.
- **Rationale**: transcribing the sequence into the test compares the extraction to a SECOND
  transcription — vacuous, and it would agree on a mis-copied per-call base (`base_dir=synth_dir` vs
  `project`), the class that bites most here, greening a check that checks nothing (the `_poc_defects`
  failure mode). Capturing from the real loop is the only honest oracle. Precedent exists:
  `test_synthesize_smoke_uses_relative_import` captures a written file via a `run_tests` stub.
- **Alternatives**: transcription — rejected (vacuous); loop-level event tests only — rejected (coarse,
  duplicate the 031/032 tests, don't pin the sequence OUTPUT).

## Decision 3 — Four commits, each independently green, each guarantee named (FR-013)

- **Decision**: extract (gated by FR-014) → swap+drop-gate → move-utils → move-fixers+arch-test. Each is
  its own reviewable, green commit; SC-006's no-op-diff bar is per-commit.
- **Rationale**: the steps have DIFFERENT guarantees, and the riskiest (rewriting two of the harness's
  largest function bodies) is not covered by the characterization tests it creates — so it gets its own
  gate (FR-014) and its own commit. A single mega-diff would be unreviewable as a no-op.

## Decision 4 — The architecture test keys on the named-function SET, not line numbers (FR-009)

- **Decision**: assert the set of named sequence-functions BY NAME and that the individual fixers are
  called only from inside them.
- **Rationale**: line-number keying breaks on any unrelated refactor and gets weakened; a name-set
  assertion is a stable STRUCTURAL invariant — a sixth site means adding a named function + updating the
  set, a conscious declared change.

## Testing approach

- **Characterization** (`test_solidity_fixers.py`): each named sequence-function over a fixed
  forge-output + code fixture → asserted output. Green pre-move (functions extracted in commit 1) and
  after (functions moved in commit 4). Includes pinning the drafting in-place ABSENCE of `import_paths`.
- **Temporary differential** (commit 1 only): capture-from-real-loop vs named function, byte-identical;
  removed in commit 2.
- **Architecture** (`test_fixer_sites.py`): the named-function set + no stray fixer call.
- **Existing suite**: the primary oracle — must stay green at every commit; no test LOGIC edits (import
  lines only if a symbol moved and is not re-exported).
