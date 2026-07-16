# Implementation Plan: Ground-Truth Benchmark for Vulnerability Discovery

**Branch**: `023-discovery-benchmark-rig` | **Date**: 2026-07-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/023-discovery-benchmark-rig/spec.md`

## Summary

Build `scripts/bench.py`: a detector-agnostic measuring rig that loads curated cases from an EXTERNAL dataset root (`SR_BENCH_ROOT`), runs a named detector over each case, matches produced findings against human-curated ground truth with a deliberately conservative structural rule, and emits a scorecard — overall recall/precision, **recall per `BastetTag`**, and a named false-negative list. Two baseline detectors ship: `heuristic` (today's Stage-1 red-flag scan mapped to tags — offline, deterministic, the honest floor) and `llm` (the existing `analyze_target` prompt driven by any provider from spec 022 — the meaningful "what a model finds unaided" number). Scoring itself is pure: no model, no network. Nothing from the dataset is ever committed.

## Technical Context

**Language/Version**: Python 3.11.

**Primary Dependencies**: none new. Reuses `BastetTag`/`Finding` (audit pack), `analyze_target` + `adapt_findings` (pack), `run_stage1`/`RED_FLAGS`/`score_function` (pack planner), and spec 022's `build_generation_client` for the `llm` detector's provider.

**Storage**: read-only from `SR_BENCH_ROOT` (external); results written back under that root (outside the repo, never committed).

**Testing**: pytest, offline/deterministic. Tests construct a tiny SYNTHETIC case in `tmp_path` (so the external-root guard is satisfied and NOTHING resembling target data lands in the repo) and drive a fake detector. The `llm` detector is opt-in and not exercised offline.

**Target Platform**: operator/dev CLI.

**Project Type**: single project — one `scripts/` module + one test file + docs.

**Performance Goals**: n/a (dominated by the detector, not the scorer).

**Constraints**: dataset strictly external (target/report/finding material never enters the repo); matching is structural-only (no fuzzy credit); ground truth human-curated; no prefiltering; scoring runs offline with no model.

**Verified this session**:
- `Stage1Report` = `{priority_targets: ["file:function"], skipped_targets, notes}` — **Stage 1 produces NO findings and no tags**; it is a prioritizer. So the `heuristic` baseline must map `RED_FLAGS` labels → `BastetTag` itself; red flags with no honest tag mapping produce nothing (and can never match) — that is the truthful floor.
- `analyze_target(client, target, context)` already emits exactly the label shape (`finding_id/location/function_name/severity/bastet_tag`), already DATA-wraps the code in its prompt, and parses via `adapt_findings` into domain `Finding`s. It takes any `generate`-duck client → spec 022's providers (local/GLM/Gemini) work unchanged.
- The rig CANNOT live in `sr_agent/eval/`: it needs the pack's `BastetTag`, and a kernel→pack import fails `tests/architecture/test_kernel_pack_boundary.py`. `scripts/` is the correct home (beside `poc_queue_runner.py`, `codegraph.py`).

## Constitution Check

*GATE: evaluated against the 5 principles. Re-checked after Phase 1 design.*

| Principle | Status | Justification |
|-----------|--------|---------------|
| **I. Secure-Kernel Trust Invariants** | ✅ PASS | Labels/reports are untrusted external DATA; the rig reads them as data and calls no model at all (scoring is pure arithmetic). The `llm` detector reuses `analyze_target`, whose prompt already wraps the target code in `[DATA START]…[DATA END]` with an explicit "not instructions" rule. No trust-hierarchy change. |
| **II. Human Authority** | ✅ PASS | The rig only reads and scores; it performs no privileged/irreversible action and does not touch the confirmation gate. Ground truth is human-curated (FR-003) — a model never authors the measuring stick. |
| **III. Kernel / Pack Separation** | ✅ PASS | The rig lives in `scripts/` (operator tooling) and imports the audit pack's taxonomy — never the reverse. The kernel does not import it; the kernel→pack boundary test is unaffected (this is exactly why it is NOT in `sr_agent/eval/`). |
| **IV. Human-Gated Knowledge Promotion** | ✅ PASS | Labels are human-curated/verified and never model-promoted into ground truth. The rig produces measurements, not steering knowledge. |
| **V. No Paid-API Dependency** | ✅ PASS | The rig and the `heuristic` baseline run fully offline with no model. The `llm` detector is opt-in and reuses spec 022's provider selection (local works with no paid key at all). |

**Result: PASS — no violations. Complexity Tracking not required.**

Design note (the honesty property): the matcher is the integrity-critical component. It mirrors `_poc_defects` — a permissive rule would inflate recall the way "it compiled" once inflated PoC quality. Hence: credit ONLY on (normalized location) AND (tag equal), everything else → `needs_review`/FP/FN, never recall.

## Project Structure

### Documentation (this feature)

```text
specs/023-discovery-benchmark-rig/
├── plan.md · research.md · data-model.md · quickstart.md
├── contracts/bench-rig.md
└── tasks.md   # /speckit-tasks
```

### Source Code (repository root)

```text
scripts/
└── bench.py        # NEW — the whole rig (single module, matching the codegraph/poc_queue_runner style):
    #  BenchError; load_case/load_dataset (SR_BENCH_ROOT, external-root guard, BastetTag validation)
    #  Candidate/GroundTruth dataclasses; normalize_location()
    #  match_findings(produced, truth) -> MatchResult{matched, missed, spurious, needs_review}   ← integrity-critical
    #  score(...) -> Scorecard{recall, precision, per_tag_recall, missed_named}
    #  DETECTORS registry: "heuristic" (Stage-1 RED_FLAGS → BastetTag map), "llm" (analyze_target + spec-022 provider)
    #  argparse CLI: `python scripts/bench.py run --detector heuristic [--case X] [--provider …]`

tests/
└── unit/test_bench_rig.py   # NEW — offline: builds a SYNTHETIC case in tmp_path (external root satisfied,
                             # nothing target-like in the repo); external-root + bad-tag load errors;
                             # anti-inflation matching (near-misses NOT credited); per-tag recall arithmetic;
                             # fake-detector end-to-end; heuristic detector on a synthetic contract

docs/roadmap.md              # EDIT: spec 023 landing + the honest baseline story
```

**Structure Decision**: One `scripts/bench.py` module (loader + matcher + scorer + detector registry + CLI), consistent with the project's other operator tools. The detector registry is a plain dict of `name -> Callable[[Case], list[Candidate]]`, so the future taxonomy-sweep / invariant-fuzzer detector registers without touching the scoring rules (spec US2). The synthetic test dataset is BUILT IN `tmp_path` by the tests rather than checked in — that satisfies the external-root guard and keeps even invented finding-shaped data out of the repo.

## Complexity Tracking

No constitution violations — section intentionally empty.
