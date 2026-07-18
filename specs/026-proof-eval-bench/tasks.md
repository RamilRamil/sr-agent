# Tasks: Proof-Pipeline Eval

**Feature**: `026-proof-eval-bench` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: one new module (`scripts/proof_bench.py`), one unit test file, one architecture guard test.
No change to `poc_queue_runner.py` or any kernel/pack code. No new dependencies (stdlib only).

**Tests ARE requested** — FR-017 makes offline deterministic tests part of the feature, so each story
writes its tests before its implementation.

**Non-negotiable test rule**: the real harness run is NEVER exercised in tests — it is the expensive
measured subject, stubbed at the `run_case` seam. Scoring is tested on SYNTHETIC manifests + scripted
harness outcomes only.

**Fixture rule (non-negotiable, every test task)**: fixtures are **invented** — case manifests, event
streams, contract/finding names — reproducing only the SHAPE of real data. No target material enters
the repo (memory `feedback_no_target_code_in_agent`; enforced by `test_no_target_material.py`).

---

## Phase 1: Setup

- [X] T001 [P] Create `tests/unit/test_proof_bench.py` with a docstring naming feature 026, the offline/synthetic-fixture contract, and a `_write_case(root, case_id, **fields)` helper that lays out a synthetic `cases/<id>/case.json` in a tmp dir
- [X] T002 [P] Create `tests/architecture/test_proof_bench_no_model.py` with a docstring stating it guards FR-007/FR-013: the scoring path performs no model call; only `run_case` (subprocess) may reach the harness

---

## Phase 2: Foundational (dataclasses + external-only loading)

**Purpose**: the entities and the loud, external-only loader every story builds on. Mirrors bench.py.

- [X] T003 Create `scripts/proof_bench.py` with a module docstring (proof axis, sibling to bench.py not an extension) and the dataclasses: `Case` (case_id, target_path, report_path, finding_id, fix_path — NO `is_lead`: the set holds only confirmed fix-bearing findings; a lead is promoted-or-discarded before it becomes a case, FR-009), `RunConfig` (case_set_id, model, provider, scaffold, example, settings, n, harness_version), `CaseOutcome` (case_id, run_idx, stage, outcome, verify_reason — comment that `stage == verified` IFF `outcome == passed_verified`, so the funnel top and the interval numerator cannot drift), `Interval` (lo, hi, mass, successes, trials), `Funnel` (per-stage survivor counts + named casualties), `Report` (interval, funnel, config) — each with `to_dict()` like bench.py's `Scorecard`
- [X] T004 Add `ProofBenchError(Exception)` and `_external(p, what) -> Path` to `scripts/proof_bench.py`, copying bench.py's guard exactly (`_AGENT_ROOT` check; reject any path == or under the agent repo) — no dataset/target/fix content ever in the repo (FR-012)
- [X] T005 Add `load_case(case_dir)` / `load_dataset(root)` to `scripts/proof_bench.py`: resolve `SR_PROOF_ROOT`, validate external, parse `case.json`; a case missing `fix_path` (or whose fix file does not exist) is a LOUD `ProofBenchError`, never a skip — UNCONDITIONALLY, since every case is a confirmed fix-bearing finding (FR-008; leads are promoted-or-discarded before becoming cases, FR-009)

### Tests for Phase 2

- [X] T006 [P] Test in `tests/unit/test_proof_bench.py`: `_external` rejects a dataset root inside the agent repo (reuses bench.py's guard shape)
- [X] T007 [P] Test in `tests/unit/test_proof_bench.py`: a case manifest with no `fix_path`, and one whose fix file is absent, each raise `ProofBenchError` loudly (FR-008) — never load silently
- [X] T008 [P] Test in `tests/unit/test_proof_bench.py`: a valid synthetic case (all fields, fix file present) loads correctly; there is no lead-case path — every loaded case is fix-bearing (the missing-fix rejection is T007)

**Checkpoint**: entities + loud external loader exist; T006–T008 pass.

---

## Phase 3: User Story 1 — a number that admits doubt (Priority: P1)

**Goal**: the verified fraction as a credible interval that widens with smaller N, plus an overlap test.

**Independent test**: `credible_interval(s, n)` matches known Beta anchors and widens as N shrinks;
`compare` reports overlap vs separation.

### Tests for User Story 1

- [X] T009 [P] [US1] Test in `tests/unit/test_proof_bench.py`: `credible_interval` anchors — for a uniform posterior the 0.5-quantile is 0.5 and the 0.025-quantile ≈ 0.025 (within tolerance); a symmetric posterior's median is 0.5 (validates the betai + bisection core)
- [X] T010 [P] [US1] Test in `tests/unit/test_proof_bench.py`: determinism — `credible_interval(s, n)` returns byte-identical endpoints across two calls (FR-016)
- [X] T011 [P] [US1] Test in `tests/unit/test_proof_bench.py`: the widening property — the interval for `(s=1, n=2)` is strictly WIDER than for `(s=10, n=20)` (same rate, less data → more doubt) (FR-003)
- [X] T012 [P] [US1] Test in `tests/unit/test_proof_bench.py`: edge cases — `s=0` and `s=n` produce bounded, sensible intervals (Jeffreys does not collapse), and `n=1` yields a wide interval (US1 scenario 4)
- [X] T013 [P] [US1] Test in `tests/unit/test_proof_bench.py`: `compare` on two intervals — overlapping → "not distinguishable"; disjoint → the decided direction (US1 scenarios 2/3)

### Implementation for User Story 1

- [X] T014 [US1] Implement the regularized incomplete beta in `scripts/proof_bench.py`: `_betacf(a, b, x)` (Lentz continued fraction) and `_betai(a, b, x)` (normalized via `math.lgamma`), with fixed iteration cap + tolerance for determinism
- [X] T015 [US1] Implement `credible_interval(successes, trials, mass=0.95)` in `scripts/proof_bench.py`: Jeffreys posterior `Beta(s+0.5, trials-s+0.5)`, each endpoint by bisection on `_betai` to a fixed tolerance; comment WHY Jeffreys (bounded at s=0/s=trials — the small-N regime; research Decision 2/3)
- [X] T016 [US1] Implement `compare(a: Report, b: Report)` overlap logic in `scripts/proof_bench.py`: intervals disjoint → decided direction; overlapping → "not yet distinguishable" — never a false winner (FR-004) (config-mismatch guard lands in US4)

**Checkpoint**: US1 independently testable — T009–T013 pass.

---

## Phase 4: User Story 2 — see WHERE proofs die (Priority: P1)

**Goal**: a per-stage attrition funnel with named casualties, monotonic by construction.

**Independent test**: `build_funnel` over scripted case-runs yields correct non-increasing survivor
counts and names the cases that did not advance.

### Tests for User Story 2

- [X] T016b [P] [US2] Test `_stage_of` DIRECTLY on scripted raw EVENT streams (not pre-staged outcomes): a stream reaching `task_done==passed_verified` → `verified`; one with `tested.real_pass=true` but `task_done != passed_verified` → `real_pass`; one with `tested.compiled=true` only → `compiled`; a `written` but never-compiled stream → `draft`. This pins the fragile coupling to the runner's real event shapes — the analog of reconstruct's "real git apply" rule (do not test only the pre-staged aggregation)
- [X] T016c [P] [US2] Test `_stage_of` membership: a case whose finding_id IS in the `extracted` event's `ids` reaches at least `extracted`; a case whose finding_id is ABSENT (or an `only_ids_not_found` event fired) is an extraction-stage death, NOT a survivor (extraction emits ALL ids, so a bare `extracted` event must not count every case as extracted — research Decision 4/5)
- [X] T017 [P] [US2] Test in `tests/unit/test_proof_bench.py`: `build_funnel` over a scripted set of `CaseOutcome`s produces correct per-stage survivor counts and the NAMED cases that died at each stage (US2 scenario 1)
- [X] T018 [P] [US2] Test in `tests/unit/test_proof_bench.py`: funnel counts are monotonically non-increasing down the stages for any scripted set (FR-006, US2 scenario 2)
- [X] T019 [P] [US2] Test in `tests/unit/test_proof_bench.py`: a real_pass-but-not-verified set makes the `real_pass → verified` cliff visible and attributes the casualties to the verification stage (US2 scenario 3 — this session's exact situation)
- [X] T020 [P] [US2] Test in `tests/unit/test_proof_bench.py`: a `run_error` / `only_ids_not_found` case-run lands in its own attrition bucket, counted as neither success nor a proving-failure (edge case)

### Implementation for User Story 2

- [X] T021 [US2] Implement `_stage_of(events, finding_id) -> stage` in `scripts/proof_bench.py`: map one case-run's harness events to the FURTHEST stage reached (`extracted → draft(written) → compiled(any tested.compiled) → real_pass(any tested.real_pass) → verified(task_done==passed_verified)`). CRITICAL: "extracted" requires `finding_id` to be IN the `extracted` event's `ids` list (extraction emits all ids; a bare event does not qualify) — research Decision 4/5. `run_error`/`sandbox_unavailable`/`only_ids_not_found`/timeout → their own bucket, neither success nor proving-failure
- [X] T022 [US2] Implement `build_funnel(outcomes) -> Funnel` in `scripts/proof_bench.py`: aggregate survivor counts per stage (non-increasing by construction) + the named non-advancing cases per stage (FR-005)

**Checkpoint**: US2 independently testable — T017–T020 pass.

---

## Phase 5: User Story 3 — cannot inflate its own number (Priority: P1)

**Goal**: verified counts exactly the harness-reported `passed_verified`; no model in scoring.

**Independent test**: `score` counts exactly the verified outcomes; the architecture guard confirms no
model in the scoring path.

### Tests for User Story 3

- [X] T023 [P] [US3] Test in `tests/unit/test_proof_bench.py`: `score` over scripted outcomes counts as verified EXACTLY the case-runs whose outcome is `passed_verified` — a `passed_unchecked` or `unverified_pass` is never counted (US3 scenario 1, FR-007, SC-005)
- [X] T024 [P] [US3] Test in `tests/unit/test_proof_bench.py`: the verified-trials denominator equals exactly the loaded (all fix-bearing) case-runs — since a fix-less case is rejected at load (T007), there is no lead/fix-less case silently included in or excluded from the denominator (FR-008/FR-009 boundary)
- [X] T025 [US3] Test in `tests/architecture/test_proof_bench_no_model.py`: AST — the scoring functions (`credible_interval`, `_betai`, `build_funnel`, `compare`, `score`, `render`) import no LLM client and call no `generate`; only `run_case` may (via subprocess). Mutation note: this test must FAIL if a client import is added to the module top level

### Implementation for User Story 3

- [X] T026 [US3] Implement `score(outcomes, config) -> Report` in `scripts/proof_bench.py`: verified trials = case-runs of non-lead, fixed cases; successes = those with outcome `passed_verified` EXACTLY; assemble the credible interval (FR-002) + funnel into a `Report`. Pure — no model, no I/O
- [X] T027 [US3] Implement `run_case(case, config) -> list[CaseOutcome]` in `scripts/proof_bench.py`: build the runner argv (`--only <finding_id> --fix-patch <finding_id>=<fix_path> --project --report --provider --model --test-scaffold --example-poc --image --fork --max-minutes`), subprocess it N times (FR-001), parse JSON events from captured stdout into `CaseOutcome`s. Comment that this is the SOLE impure/expensive seam and the only thing tests stub (research Decision 1)

**Checkpoint**: US3 independently testable — T023–T025 pass; the number cannot be inflated.

---

## Phase 6: User Story 4 — catch incomparable comparisons (Priority: P1)

**Goal**: each result records its config; comparing across configs differing beyond harness version is flagged.

**Independent test**: two result sets differing in more than harness version → `compare` flags it.

### Tests for User Story 4

- [X] T028 [P] [US4] Test in `tests/unit/test_proof_bench.py`: a written result set contains the full `RunConfig` (case set, model, scaffold/example, settings, N, harness version) (FR-010, US4 scenario 1)
- [X] T029 [P] [US4] Test in `tests/unit/test_proof_bench.py`: `compare` of two results differing in anything other than `harness_version` (e.g. different case set or model) is FLAGGED — no delta presented as trustworthy (FR-011, US4 scenario 2)
- [X] T030 [P] [US4] Test in `tests/unit/test_proof_bench.py`: `compare` of two results identical in config except `harness_version` proceeds and reports the interval relationship (US4 scenario 3)

### Implementation for User Story 4

- [X] T031 [US4] Extend `compare` in `scripts/proof_bench.py`: before the interval overlap test, diff the two `RunConfig`s on every field except `harness_version`; on any difference return a FLAGGED mismatch result (no trusted delta) with the differing fields named; comment this is the exact guard the "3/5 vs 2/5" misread lacked

**Checkpoint**: all four stories independently testable.

---

## Phase 7: Polish & Cross-Cutting

- [X] T032 [US1] Implement `render(report) -> str` in `scripts/proof_bench.py`: human-readable — the interval `[lo,hi]` + its width, the funnel with named casualties, and a REQUIRED caveat line stating strata-bb is a tuned-on DEV set measuring within-set regression/progress, not absolute capability (FR-014, SC-008)
- [X] T033 Add `write_result(root, report)` (external, machine-readable, alongside render's human-readable form — FR-015, like bench.py) and the CLI to `scripts/proof_bench.py`: `run` (score a case set at N) and `compare` (two result files) subparsers, mirroring bench.py's `main(argv)` shape
- [X] T034 [P] Test in `tests/unit/test_proof_bench.py`: `render` output contains N, the interval width, and the DEV-set/contamination caveat for any report (SC-008)
- [X] T035 Run `pytest tests/unit/test_proof_bench.py tests/architecture/test_proof_bench_no_model.py -q` — all pass offline with no model, container, or network (SC-007)
- [X] T036 Run the full suite `pytest -q` and confirm zero regressions (this feature adds files only; no existing code changed)
- [X] T037 [P] Verify the guards can fail by mutation: break the Jeffreys prior to a uniform `Beta(s, n-s)` and confirm the `s=0` edge test FAILS; make `score` count `passed_unchecked` as verified and confirm T023 FAILS; add a top-level client import to `proof_bench.py` and confirm T025 FAILS — then revert all three (SC-005)
- [X] T038 [P] Add a landing entry to `docs/roadmap.md` for spec 026: proof quality is now measurable (interval + funnel), sibling to bench.py; the "3/5 vs 2/5" misread is what it prevents (pinned config + overlap test); strata-bb is an honestly-labelled DEV set; no model in scoring (guarded); the stdlib Jeffreys interval (no scipy)
- [X] T039 Confirm no target material entered the repo: review `git diff --stat`, verify every fixture name in the new tests is invented, and `pytest tests/architecture/test_no_target_material.py -q` passes

---

## Dependencies & Execution Order

```
Phase 1 Setup (T001, T002)
   └─> Phase 2 Foundational (T003 → T004 → T005 → T006–T008)   ← BLOCKS all stories
          ├─> Phase 3 US1 (T009–T013 → T014 → T015 → T016)
          │      └─> Phase 6 US4 (T028–T030 → T031)             ← extends compare from US1
          ├─> Phase 4 US2 (T017–T020 → T021 → T022)
          └─> Phase 5 US3 (T023–T025 → T026 → T027)             ← score uses interval + funnel
                 └─> Phase 7 Polish (T032 → T033 → T034 → T035 → T036 → T037, T038, T039)
```

- **Phase 2 blocks everything**: dataclasses + loader underlie every metric.
- **US1 → US4**: US4 extends the `compare` function US1 introduces (config-mismatch gate before overlap).
- **US1 + US2 → US3**: `score` assembles the interval (US1) and funnel (US2), so US3 lands after both.
- **US1 ∥ US2**: independent after Phase 2 — interval math vs event→stage mapping, no shared state.
- **run_case (T027)** depends on nothing in scoring; it is the seam and can land anytime after Phase 2,
  but is grouped with US3 since that phase completes the end-to-end path.

## Parallel Opportunities

- **T001, T002** — [P]; two different new files.
- **T006–T008**, **T009–T013**, **T016b–T016c + T017–T020**, **T023–T024**, **T028–T030** — [P] within each group.
- **T037, T038** — [P]; different files (tests vs `docs/roadmap.md`).

## Implementation Strategy

**MVP = Phase 1 + Phase 2 + Phase 3 (US1) + Phase 5 (US3) + minimal render/CLI**. That yields a
trustworthy verified-fraction interval you can actually run — the headline number that answers "better?"
with honest doubt. US3 (cannot inflate) ships WITH it, not after — an inflatable number is worse than none.

**Increment 2 = Phase 4 (US2)** — the funnel. Turns "we regressed" into "we regressed HERE".

**Increment 3 = Phase 6 (US4)** — the config-mismatch guard. Cheap, and it is the specific discipline
whose absence caused the motivating misread.

**Total**: 41 tasks — 2 setup, 6 foundational, 8 US1, 8 US2 (incl. the direct `_stage_of` event-stream tests), 5 US3, 4 US4, 8 polish.
