# Research: Proof-Pipeline Eval (spec 026)

Every decision grounded in the current code (bench.py, poc_queue_runner.py) and captured 2026
eval practice (memory `reference_eval_practices_2026`, `project_proof_eval_design`).

## Decision 1: The harness is measured as a BLACK BOX via subprocess — not refactored

**Finding**: `poc_queue_runner` has no programmatic entry — only `main()` (argparse), which runs the
whole report. But it already exposes exactly the two flags this needs: `--only <finding_id>` (filters
to one finding, matched lowercased at line 2661) and `--fix-patch <id>=<path>` (spec 025, the operator
fix). And it prints every event as a JSON line to **stdout** (line 2576), not just to the progress
file.

**Decision**: `proof_bench` invokes the runner as a **subprocess** per case-run, with the pinned
flags, and parses the events from captured stdout. It does NOT import or refactor the runner.

**Rationale**: the spec forbids changing the harness, and measuring it through its real operator
interface is philosophically correct — the eval scores the harness AS SHIPPED, not a special-cased
in-process variant. stdout gives clean per-invocation isolation (the progress file appends across
runs; stdout does not). Runs are sequential (they share `audit/poc/` scratch and would collide).

**Alternatives considered**: extract a `run_one()` callable from the runner — rejected, it changes
the harness (out of scope) and couples the eval to internal structure; reading the appended progress
file — rejected, needs run-boundary bookkeeping that stdout capture makes free.

## Decision 2: Statistical unit = the case-run; pooled Jeffreys Beta credible interval

**Finding**: no scipy/numpy in the venv (checked); `math.lgamma` is available. The spec fixes the
PROPERTY (Bayesian, widens with smaller N, supports an overlap test, deterministic), leaving the
estimator to planning.

**Decision**: the Bernoulli trial is a **case-run** (case × one run). Over a set of C cases at N runs
each, trials = C·N, successes = count of `passed_verified`. The primary metric is the posterior over
that pooled rate p, reported as an equal-tailed **95% Jeffreys credible interval**: posterior
`Beta(s + 0.5, (C·N − s) + 0.5)`, endpoints at the 2.5% and 97.5% quantiles.

**Rationale**: Jeffreys (Beta(0.5,0.5) prior) is the standard objective-Bayes interval for a binomial
rate — excellent small-sample coverage and, crucially, it stays bounded and sensible at s=0 and s=C·N
(a uniform-prior/Wald interval collapses there, exactly the small-N regime we live in). Pooling gives
ONE comparable number ("how often does a case-run from this set yield a verified proof"), which is
what US1 compares across harness versions. Per-case heterogeneity is not lost — it surfaces in the
funnel's named casualties (Decision 3).

**Alternatives considered**: Wilson score interval (frequentist, closed-form, no deps) — rejected,
not Bayesian and the spec/design commit to a Beta posterior; per-case rate then a fraction-of-cases
interval — rejected, a fraction over 5 cases is coarser and the "Beta posterior over N runs" framing
points at pooled case-runs; posterior sampling — rejected, non-deterministic (violates FR-016).

## Decision 3: The interval endpoints via stdlib `betai` (continued fraction) + bisection

**Decision**: implement the regularized incomplete beta `I_x(a,b)` with the Numerical-Recipes
`betacf` continued fraction (Lentz), normalized via `math.lgamma`; invert to a quantile by bisection
on `[0,1]` to a fixed tolerance and iteration cap. Fully deterministic, stdlib-only (`math`).

**Rationale**: this is the one nontrivial numeric in the feature and it is textbook, ~40 lines,
well-conditioned for our a,b ≥ 0.5. Determinism (FR-016) comes from fixed tolerance + iteration cap,
not from any library. Testable against known anchors: `Beta(1,1)` (uniform) → ppf(0.5)=0.5,
ppf(0.025)=0.025; `Beta(0.5,0.5)` symmetric → ppf(0.5)=0.5; monotonic in the mass; and the feature
property — the interval for (s=1,N=2) is strictly WIDER than for (s=10,N=20) at the same rate.

**Alternatives considered**: vendoring a stats lib / adding scipy — rejected (Constitution V spirit,
and a heavyweight dep for one quantile); a normal approximation — rejected (wrong at small N, the
whole point).

## Decision 4: The attrition funnel is derived from the stdout event stream

**Finding**: per case-run the runner emits, in order: `extracted` (the finding present in the task
list), `written` (a draft was produced), `tested` (carrying `compiled` and `real_pass` booleans per
attempt), and `task_done` (carrying the final `outcome`). Earlier-stage deaths and `run_error` /
`sandbox_unavailable` outcomes are their own signals.

**Decision**: map each case-run to the FURTHEST stage it reached:
`extracted → draft(written) → compiled(any tested.compiled) → real_pass(any tested.real_pass) →
verified(task_done.outcome == passed_verified)`. The funnel aggregates survivor counts per stage over
all case-runs, plus a NAMED list of the cases that never advanced past each stage. Counts are
non-increasing by construction (a later stage is a subset of an earlier one — FR-006). A run that
errored/timed out is recorded in its own attrition bucket, neither a proving-failure nor a success
(edge case).

**Rationale**: FR-005. The funnel is the discovery benchmark's per-class breakdown applied to the
pipeline — it says WHAT to fix next. This session's real situation (many real_pass, zero verified,
because fixes never applied) is exactly the `real_pass → verified` cliff the funnel makes visible.

## Decision 5: finding_id is pinned by the run configuration, not universal

**Finding**: extraction ids are model-dependent (observed: flash-lite emits `1..5`, gemini-3 emits
`H-01..`). `--only` and `--fix-patch` both key on the finding_id, so a case manifest's `finding_id`
must match what the PINNED model's extraction produces.

**Decision**: `finding_id` is part of the case manifest AND the run configuration is pinned to a
model, so the id is stable within a comparison. Record this as an explicit assumption; a mismatch
surfaces immediately as the runner's `only_ids_not_found` event → that case-run is an extraction-stage
death in the funnel (honest, not a crash).

**Rationale**: this coupling is real and cannot be abstracted away without fuzzy finding-matching
(rejected for the same reason model-as-judge is). Pinning the model (US4's config record) makes it
deterministic; the funnel makes a mismatch visible rather than silent.

## Decision 6: Module, dataset layout, and disciplines mirror bench.py

**Decision**: `scripts/proof_bench.py`, `SR_PROOF_ROOT` (env) → `<root>/cases/<case>/case.json`
(target_path, report_path, finding_id, fix_path), results under `<root>/results/`. Reuse bench.py's
exact `_external()` guard (`_AGENT_ROOT` check) and its `BenchError`-style loud loading. Results are
written external, human- and machine-readable, like `write_result`.

**Rationale**: FR-012/FR-015 + memory `feedback_no_target_code_in_agent`. bench.py already solved
external-root validation and external result-writing for the discovery axis; the proof axis reuses
the discipline, not the code path (different instrument, Decision from spec).

## Decision 7: No model in the scoring path — pure functions, guarded

**Decision**: the scoring functions (`credible_interval`, funnel builder, comparison, render) are
PURE — outcomes in, numbers/text out. The only model/Docker/network touch is the subprocess harness
run, behind a single seam (`run_case`) that the offline tests stub. Add an architecture guard
(mirroring `test_verification_no_model.py`) that `proof_bench`'s scoring functions import no client
and call no `generate`.

**Rationale**: FR-007/FR-013 + SC-005/SC-007. This is US3's load-bearing property. A model in scoring
would let the number be argued up — the exact failure model-as-judge represents, rejected for the
discovery benchmark for the same reason.

## Test-fixture rule (non-negotiable)

Offline tests use invented case manifests and SCRIPTED harness outcomes (fake event streams / fake
`run_case` returns) — never a real harness run, never real target material. The strata-bb case set
and its operator fixes ground the design and live OUTSIDE the repo; only synthetic shapes enter tests
(memory `feedback_no_target_code_in_agent`; enforced by `test_no_target_material.py`).
