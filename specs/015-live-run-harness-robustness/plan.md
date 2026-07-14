# Implementation Plan: Live-Run Harness Robustness

**Branch**: `015-live-run-harness-robustness` | **Date**: 2026-07-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/015-live-run-harness-robustness/spec.md`

## Summary

Three harness-only fixes for failure modes the first live H-01 run surfaced: (1) extract the
real Solidity span from prose-wrapped model output — never write a prose-only or empty PoC;
tool-mode empty → marker fallback; (2) proactively expand the field lists of struct/enum
types referenced by a finding's `callable_api` into the draft grounding (research finding R2:
the on-demand lookup already returns fields — the model just constructs before it looks up);
(3) tighten the spec-014 lesson-capture trigger to fire only on real compile progress, never
on a lateral/regression error-change. All in `scripts/poc_queue_runner.py` (+ a small assist
from `scripts/solidity_index.py` for struct expansion). No security invariant, DATA-wrap
rule, trust hierarchy, or promotion gate changes. Offline-tested; no new dependency.

## Technical Context

**Language/Version**: Python 3.11+ (existing).

**Primary Dependencies**: none new. Reuses `scripts/solidity_index.py` (`SymbolIndex`,
`_render_struct`/`_render_enum`, `Symbol.definition`), the spec-009 fake-model/fake-sandbox
test harness, and the spec-014 `_maybe_capture_lesson` hook.

**Storage**: N/A (no persistence change).

**Testing**: pytest, offline. New `tests/unit` for the Solidity extractor + the capture
trigger; `tests/integration` (spec-009 fake harness) for prose→clean-PoC, tool→marker
fallback, and the capture transitions; a `SymbolIndex` fixture for proactive struct
expansion. No model, Docker, network (FR-008).

**Target Platform**: local dev; CI-safe.

**Project Type**: single project — edits to `scripts/poc_queue_runner.py` (extractor + its
draft/fix/tool/lookup callers, the grounding builder, the capture trigger) and a small
helper in `scripts/solidity_index.py` (expand referenced struct/enum definitions).

**Performance Goals**: N/A (string processing + a bounded index walk).

**Constraints**: behavior-preserving on the happy path (a clean fenced reply extracts
identically); no new dependency; struct expansion is budget-bounded (prompt bloat guard);
the on-demand lookup response is unchanged (FR-005); no kernel-invariant change (FR-009).

**Scale/Scope**: one extractor rewrite + ~3 call-site updates; one grounding-expansion
helper; one capture-trigger tightening; the offline tests above.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Secure-Kernel Trust Invariants** — PASS. No change to DATA-wrapping, the `SourceType`
  hierarchy, memory HMAC, or the tool-call budget. The Solidity extractor only trims model
  output to code before it is written to the (sandboxed) PoC file; struct expansion injects
  *real target source definitions* (already DATA-treated grounding) into the draft prompt;
  the capture-trigger fix makes the spec-014 loop record fewer/cleaner candidates — all still
  low-trust, still human-gated. FR-009 pins this.
- **II. Human Authority** — PASS. No privileged/irreversible action; lesson promotion stays
  out-of-band and human-gated (untouched).
- **III. Kernel / Capability-Pack Separation** — PASS. All changes are in the PoC harness
  (eval tooling) and its Solidity-index helper; no kernel/pack boundary is touched.
- **IV. Human-Gated Knowledge Promotion** — PASS, and reinforced. Tightening the capture
  trigger keeps junk out of the candidate queue; promotion remains a human command.
- **V. No Paid-API Dependency** — PASS. Offline; the tool→marker fallback uses the existing
  local protocols; no API; validation offline (FR-008).

No violations — **Complexity Tracking empty**. This is the constitution's "test-first for
security-critical behavior" applied to harness hardening (the capture-trigger correctness
and the no-empty-PoC guarantee are each written as a failing test first).

## Project Structure

### Documentation (this feature)

```text
specs/015-live-run-harness-robustness/
├── plan.md              # This file
├── research.md          # Phase 0 (R1–R5; R2 corrects the US2 hypothesis)
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1 (extractor, grounding-expansion, capture-trigger)
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
scripts/poc_queue_runner.py
├── _extract_solidity(text)          # NEW (replaces _strip_fences): span from first
│                                     #   Solidity token → last; "" when no code (US1)
├── draft() / fix()                  # write only on non-empty extraction; else failed draft
├── _generate_with_lookups / _generate_with_tool_calls
│                                     #   use _extract_solidity; tool→marker fallback (US1)
├── _grounding() / callable-api build #  inject expanded struct/enum defs (US2)
└── _maybe_capture_lesson(...)        # require compiled/real_pass progress (US3)

scripts/solidity_index.py
└── expand_referenced_types(...)      # NEW helper: given callable_api text + index,
                                      #   return the struct/enum definitions it references
                                      #   (one level of nesting), reusing _render_struct/_render_enum

tests/
├── unit/test_solidity_extract.py         # prose-prefix/-only/trailing, no-token → "" (US1)
├── unit/test_capture_trigger.py          # stuck→compiled ⇒ capture; stuck→other-error ⇒ none (US3)
├── integration/test_poc_extract_prose.py # spec-009 harness: prose reply → clean PoC / failed draft (US1)
├── integration/test_tool_empty_fallback.py # tool round-trip empty → marker fallback (US1)
└── unit/test_struct_grounding.py         # callable_api → grounding includes nested struct fields (US2)
```

**Structure Decision**: Single project. The core change is one robust `_extract_solidity`
replacing `_strip_fences` at every code-extraction site, plus a bounded struct/enum
expansion helper feeding the draft grounding, plus a one-line-of-logic tightening of the
spec-014 capture trigger. `scripts/solidity_index.py` gains a small pure helper that reuses
its existing renderers. Everything is offline-testable through the spec-009 fake harness and
`SymbolIndex` fixtures.

## Complexity Tracking

*No Constitution Check violations — intentionally empty.*

**Post-design re-check (after Phase 0/1)**: research.md's decisions (span-based extractor +
no-empty-write + tool→marker fallback; proactive struct expansion instead of a lookup change;
compile-gated capture) introduce no new violations — still PASS; US1/US3 reinforce Principles
I and IV, US2 is pure grounding quality.
