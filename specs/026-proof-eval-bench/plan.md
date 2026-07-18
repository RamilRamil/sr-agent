# Implementation Plan: Proof-Pipeline Eval

**Branch**: `026-proof-eval-bench` | **Date**: 2026-07-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/026-proof-eval-bench/spec.md`

## Summary

An instrument that measures PROOF quality, sibling to the discovery benchmark. It runs the existing
harness (as a black box, via its `--only`/`--fix-patch` interface) N times per case over an external
case set, and reports two things: the PRIMARY metric — the pooled fraction of case-runs reaching
`passed_verified`, as a **Jeffreys Beta credible interval** that widens with smaller N and supports an
overlap test; and the DIAGNOSTIC metric — a per-stage **attrition funnel** (extract → draft →
compiled → real_pass → verified) with named casualties, saying WHAT to fix next.

It enforces the disciplines the "3/5 vs 2/5" misread taught: a run records its full configuration and
a comparison across incomparable configs is flagged (US4); the verified count is exactly what the
harness reports, never inferred or model-judged (US3); and the output states plainly that strata-bb is
a contaminated DEV set, measuring within-set regression/progress, not absolute capability (FR-014).

Grounded in [research.md](research.md): the harness stays a black box (subprocess + stdout events); the
interval is stdlib-only (`betai` continued fraction + bisection — no scipy); the scoring path has no
model, guarded by a test.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: none new — stdlib `math`/`subprocess`/`json`. Explicitly NO scipy/numpy
(absent from the venv; the Beta quantile is implemented in-repo).

**Storage**: external dataset root `SR_PROOF_ROOT` (cases in, results out) — never in the repo.

**Testing**: pytest, offline; scoring tested on SYNTHETIC manifests + scripted harness outcomes; the
real harness run is stubbed (it is the expensive measured subject, not part of the scorer).

**Target Platform**: operator CLI (`scripts/proof_bench.py`), macOS/Linux

**Project Type**: single project — operator tooling on top of the kernel/pack, like `bench.py`

**Performance Goals**: N/A for scoring (pure, instant). Harness runs are ~2–4 min each; total = C·N
runs, surfaced by the tool, not optimized by it.

**Constraints**: scoring fully offline, no model/network (FR-013); deterministic metrics (FR-016);
external-only dataset (FR-012).

**Scale/Scope**: one new module (~250 lines) + one architecture guard test + one unit test file. No
change to `poc_queue_runner.py` or any kernel/pack code.

## Constitution Check

| Principle | Status | Rationale |
|---|---|---|
| **I. Secure-Kernel Trust Invariants** | ✅ PASS | The scorer consumes the harness's own reported outcomes as tool output; it promotes nothing and introduces no new source type. Attacker-influenced code (the PoCs) runs only inside the harness's existing Docker sandbox during the measured run — the scorer never executes target code. |
| **II. Human Authority** | ✅ PASS | No privileged/irreversible action. Findings remain confirmed only by a passing (here, verified) PoC — this instrument MEASURES that, it does not weaken it. The operator fix that grounds verification is human-authored (spec 025 US2). |
| **III. Kernel / Pack Separation** | ✅ PASS | New operator tooling in `scripts/`, like `bench.py`. No kernel or pack code touched; the harness is invoked as a subprocess, not imported. |
| **IV. Human-Gated Knowledge Promotion** | ✅ PASS | No knowledge-store writes. |
| **V. No Paid-API Dependency** | ✅ **STRENGTHENS** | The scoring path forbids any model (FR-007/FR-013), guarded by a test. The Beta interval is stdlib-only precisely to avoid a heavyweight dependency. The harness runs use whatever provider the operator pins — the scorer itself needs none. |

**Gate result**: PASS on all five, V strengthened. No violations; Complexity Tracking empty. (No
MI-resistance surface: the scorer adds no tool/action to any pack and executes no target code.)

## Project Structure

### Documentation (this feature)

```
specs/026-proof-eval-bench/
├── spec.md              # what & why (4 stories; contamination honesty is first-class)
├── plan.md              # this file
├── research.md          # 7 decisions (black-box subprocess, Jeffreys stdlib interval, funnel)
├── quickstart.md        # lay out a case set, run at N, read the interval + funnel, compare
├── tasks.md             # (/speckit-tasks)
└── checklists/
    └── requirements.md
```

No `data-model.md` (the entities are small dataclasses, covered below) and no `contracts/` (a CLI +
external file layout, exercised through the tool). Omitted rather than stubbed.

### Source Code (repository root)

```
scripts/
└── proof_bench.py               # NEW — the instrument
    ├── ProofBenchError          #   loud loading, like bench.BenchError
    ├── Case / RunConfig / CaseOutcome / Funnel / Interval / Report  # dataclasses
    ├── _external(p, what)       #   the SAME external-root guard as bench.py
    ├── load_case / load_dataset #   loud on missing fix (FR-008)
    ├── credible_interval(s, n)  #   Jeffreys Beta interval — stdlib betai + bisection
    ├── build_funnel(outcomes)   #   furthest-stage aggregation + named casualties
    ├── compare(a, b)            #   overlap test + config-mismatch flag
    ├── run_case(case, cfg)      #   THE SEAM: subprocess the harness, parse stdout events (stubbed in tests)
    ├── score(outcomes, cfg)     #   pure: assemble Interval + Funnel + Report
    ├── render(report)           #   human-readable, states N, width, DEV-set caveat
    └── write_result(root, ...)  #   machine-readable, external

tests/unit/
└── test_proof_bench.py          # NEW — offline, synthetic manifests + scripted outcomes

tests/architecture/
└── test_proof_bench_no_model.py # NEW — scoring path imports no client, calls no generate
```

**Structure Decision**: `scripts/proof_bench.py`, mirroring `bench.py` (spec 023 Decision 5): the rig
needs no kernel code but must stay out of the kernel (a kernel→pack/tooling import fails the boundary
test); `scripts/` is the established home for operator tooling. It reuses bench.py's DISCIPLINES
(external guard, external results) but not its code — a different instrument for a different axis.

## Design

### The statistical unit and the interval (US1)

Trial = one case-run. Over C cases at N runs, trials = C·N, successes = `passed_verified` count.
Primary metric = 95% equal-tailed **Jeffreys** credible interval: posterior `Beta(s+0.5, C·N−s+0.5)`,
endpoints = the 0.025 and 0.975 quantiles.

`credible_interval(s, n, mass=0.95)` computes each quantile by bisection on the regularized incomplete
beta `I_x(a,b)` (`betacf` continued fraction, normalized via `math.lgamma`), fixed tolerance +
iteration cap → deterministic (FR-016). Jeffreys stays bounded at s=0 and s=C·N (the small-N regime);
a uniform/Wald interval would collapse there.

`compare(a, b)`: if the two Intervals do not overlap → decided direction; if they overlap → "not yet
distinguishable" (US1 scenarios 2/3). N=1 yields a wide interval by construction — never decisive
(edge case).

### The funnel (US2)

Per case-run, `_stage_of` maps the harness's stdout events to the furthest stage reached:
`extracted → draft (written) → compiled (any tested.compiled) → real_pass (any tested.real_pass) →
verified (task_done.outcome == passed_verified)`. Two subtleties the runner's real event shapes force
(verified against the code):

- **"extracted" means the case's finding_id is IN the `extracted` event's `ids`**, not merely that an
  `extracted` event fired — extraction emits ALL findings' ids (`{"event":"extracted", "ids":[…]}`) then
  `--only` filters. A finding that was never extracted (its id absent, or `only_ids_not_found` fired)
  is an extraction-stage death, not a survivor. Getting this wrong would count every case-run as
  "extracted" (research Decision 4/5).
- **`stage` and `outcome` on a `CaseOutcome` must agree**: the `verified` stage holds IFF
  `outcome == passed_verified`. `_stage_of` derives `stage`; `score` reads `outcome`; a test pins that
  the two never disagree (so the funnel's top and the interval's numerator cannot drift apart).

`build_funnel` aggregates survivor counts (non-increasing by construction, FR-006) and the NAMED cases
that never advanced past each stage. A `run_error`/`sandbox_unavailable`/`only_ids_not_found` case-run
lands in its own attrition bucket (neither success nor a proving-failure — edge case).

### Anti-inflation (US3)

`score` counts a verified case-run ONLY when the parsed `task_done.outcome` is exactly
`passed_verified` — no inference, no model. `run_case` is the single seam touching a model/Docker;
every other function is pure. The architecture guard test pins that the scoring functions import no
client and call no `generate` (mirrors `test_verification_no_model.py`).

### Experimental hygiene (US4)

`RunConfig` records case-set id, model, scaffold/example, settings, N, and harness version (a commit
or version marker). `write_result` persists it beside the numbers. `compare` refuses (flags) when two
result sets differ in anything other than `harness_version` — the exact guard the "3/5 vs 2/5" misread
lacked.

### Contamination honesty (FR-014)

`render` always prints N, the interval width, and a fixed caveat that the case set is a tuned-on DEV
set measuring within-set regression/progress, not absolute capability. Not a footnote — a required
line of every report (SC-008).

### The harness seam (Decision 1)

`run_case(case, cfg)` builds the runner argv (`--only <finding_id> --fix-patch <finding_id>=<fix>
--project --report --provider --model --test-scaffold --example-poc --image --fork --max-minutes`),
runs it as a subprocess, and parses the JSON events from captured stdout into a `CaseOutcome`. It is
the ONLY expensive/impure function and the ONLY thing tests stub.

## Test Strategy

`tests/unit/test_proof_bench.py`, offline, synthetic fixtures only (invented manifests + scripted
event streams / `CaseOutcome`s — never a real run, never target material):

- external-root guard rejects a dataset inside the agent repo (reuses bench.py's guard shape).
- a case manifest missing its `fix_path` → loud `ProofBenchError` (FR-008), never a skip.
- **interval**: anchors — `Beta(1,1)` ppf(0.5)=0.5 / ppf(0.025)=0.025; symmetric `Beta(0.5,0.5)`
  ppf(0.5)=0.5; monotonic in mass; determinism (same (s,n) → identical endpoints); and the property —
  (s=1,n=2) strictly WIDER than (s=10,n=20).
- **funnel**: arithmetic + monotonicity on a scripted set of case-runs; a real_pass-but-not-verified
  set makes the `real_pass → verified` cliff visible and names the casualties.
- **compare**: overlapping intervals → "not distinguishable"; separated → decided direction; configs
  differing beyond `harness_version` → flagged (US4); identical-but-version → proceeds.
- **denominator**: the verified denominator is exactly the loaded (all fix-bearing) case-runs — a fix-less case is rejected at load (FR-008), so there is no lead/fix-less case to silently include or exclude (FR-009).
- **render**: every report contains N, the interval width, and the DEV-set caveat (SC-008).

`tests/architecture/test_proof_bench_no_model.py`: AST — the scoring functions import no client and
call no `generate`; `run_case` is the sole seam that may (via subprocess, not an in-process model).

## Complexity Tracking

None. The Constitution Check passes on every principle with no deviation to justify.
