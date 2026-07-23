# Feature Specification: Unify the Deterministic Fixer Sequences (DEFERRED stub)

**Feature Branch**: `034-unify-fixer-sequences` (not yet created)

**Created**: 2026-07-23

**Status**: DEFERRED — a placeholder that preserves a deliberate, measured decision deferred out of spec
033. Do NOT implement without first answering the proof-question below with evidence. (Precedent: spec
030 was kept as a DEFERRED stub with its own rationale.)

## Why this is deferred (and separate from 033)

Spec 033 is an honest NO-OP: it MOVES the deterministic fixer functions into one module and PINS each of
the five transform-application sites' sequences with characterization tests — without changing any
sequence. It deliberately does NOT unify the sequences, because the sites' differences are (at least
partly) legitimate and unifying them CHANGES behavior:

| Site | Sequence |
|------|----------|
| synthesis pre-write | `import_paths(base_dir=synth_dir)` |
| synthesis repair loop | `import_paths(base_dir=synth_dir) → nested → address_interface` |
| drafting post-model (draft/fix) | `setup_override → import_paths(project) → nested` |
| drafting in-place repair | `undeclared_import → address_interface` |

The suspicious gap: the drafting **in-place** repair step never runs `import_paths` — so if a
deterministic in-place fix (e.g. auto-import of an undeclared symbol) introduces or leaves a wrong
relative import path, it is not caught until the later post-model pass. Closing that gap MIGHT improve
compile-convergence — or might be redundant with the post-model pass and just add cost. That is an
empirical question, not a refactor.

## Proof-question (answer with evidence BEFORE building)

**Does giving the drafting in-place repair step `import_paths` (and/or `nested`) actually improve
compile-convergence on real runs — measurably — versus the current split?**

- Instrument (the run log now carries per-event timestamps + `deterministic_fix`/`postfix_imports`
  events): count, over live runs, how often an in-place deterministic fix produced code whose ONLY
  remaining compile error was an import-path/nested one that the NEXT attempt's post-model pass then
  fixed — i.e. a round that a unified in-place sequence would have saved.
- If that count is ~0 → the gap is harmless; do NOT unify (keep 033's pinned split; close this stub as
  WONT-DO with the evidence). If it is material → unify deliberately, measured, with the 033
  characterization tests updated in the SAME commit (a conscious sequence change, not a silent one).

## Scope (WHEN un-deferred)

- Introduce the single `apply_deterministic_fixes(code, forge_output, transforms, …)` helper (or a
  per-loop unified sequence) — ONLY after the proof-question is answered YES.
- Update the 033 characterization tests to the NEW pinned sequences IN THE SAME COMMIT (the sequence
  change is explicit and reviewed, never silent).
- Re-measure compile-convergence before/after (eval-first).

## Out of Scope (of this stub)

Everything — this is a placeholder. It carries the deferred decision + its proof-question so the
reasoning does not evaporate. Requires spec 033 (the move + characterization guardrail) to land first.
