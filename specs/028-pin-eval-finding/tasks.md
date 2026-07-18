# Tasks: Pin the Finding for the Proof-Eval

**Feature**: `028-pin-eval-finding` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: ~15 lines in `scripts/poc_queue_runner.py` (a `--tasks-from` flag, `load_pinned_tasks`, a
shared `_attach_fixes` helper) + ~10 in `scripts/proof_bench.py` (3 `Case` fields, loud loader,
`run_case` pins), tests, and 5 EXTERNAL curated manifests. No `sr_agent/` change.

**Tests ARE requested** — FR-011 makes the offline tests part of the feature. The harness subprocess
and any model call are NEVER run in tests (stubbed).

**Fixture rule (non-negotiable)**: findings/task files in tests are **invented** — no target name,
path, or contract identifier enters the repo (memory `feedback_no_target_code_in_agent`; guarded by
`test_no_target_material.py`). The 5 real strata-bb manifests live OUTSIDE the repo.

**Story mapping**: US1 (the eval proves a fixed finding) is the EMERGENT end-to-end outcome of US2
(harness accepts a task input) + US3 (the eval curates + pins the finding); it has no separate code,
and its acceptance is covered by the US2/US3 tests plus the run_case pinning assertion.

---

## Phase 1: Setup

- [X] T001 [P] Verify the pinned-path plumbing points before editing: confirm `main()` obtains `tasks`, then emits the `extracted` event and writes `_extracted_tasks.json` on `tasks` regardless of source (~line 2669), so swapping only the task source shares the entire tail

---

## Phase 2: User Story 2 — the harness accepts a task input (Priority: P1)

**Goal**: `--tasks-from <file>` proves a supplied task list instead of model extraction; default
untouched; the `extracted` event still fires; fixes still attach.

**Independent test**: with `--tasks-from`, `extract_tasks` is not called and the run proves the file's
tasks; without it, extraction runs as before.

### Tests for User Story 2

- [X] T002 [P] [US2] Test in `tests/integration/test_poc_runner_loop.py`: drive `main()` with `--tasks-from <synthetic file>` and `extract_tasks` monkeypatched to RAISE — the run still succeeds (extraction NOT called), and an `extracted` event is emitted carrying the file's ids (FR-001/FR-005/FR-006-inverse)
- [X] T003 [P] [US2] Test in `tests/integration/test_poc_runner_loop.py`: WITHOUT `--tasks-from`, `extract_tasks` IS called (default path unchanged) — monkeypatch it to a sentinel task list and assert it was consulted (FR-006)
- [X] T004 [P] [US2] Test in `tests/unit/test_poc_queue_runner.py`: `_attach_fixes` on a synthetic pinned task attaches `fix` (from `extract_fix_for_finding` over a synthetic report) and `fix_patch` (from an operator-patches map) — the pinned task gets the same fixes an extracted one would (FR-003/FR-004)
- [X] T004b [P] [US2] Test in `tests/integration/test_poc_runner_loop.py`: `main()` with `--tasks-from` pointing at a MALFORMED/absent file aborts cleanly — a logged `extract_failed` event and `SystemExit`, NOT a raw traceback (A1; the branch sits inside main()'s existing try/except)

### Implementation for User Story 2

- [X] T005 [US2] Extract `_attach_fixes(raw_tasks, report_text, operator_patches) -> list[dict]` in `scripts/poc_queue_runner.py` from `extract_tasks`'s tail (~lines 466–480): keep well-formed items (id + title), build the finding dict, set `fix = extract_fix_for_finding(report_text, finding)` and `fix_patch = operator_patches.get(id)`; have `extract_tasks` call it so its behavior is byte-identical
- [X] T006 [US2] Add `load_pinned_tasks(tasks_path, report_path, operator_patches)` to `scripts/poc_queue_runner.py`: read the JSON task list (the same {id,title,location,description} shape the harness writes to `_extracted_tasks.json`, FR-002), read the report text (still required for `_attach_fixes` — A2/FR-004), return `_attach_fixes(raw, report_text, operator_patches)`; a malformed/empty file raises `json.JSONDecodeError`/`OSError`, caught by main()'s existing try (T007) as a clean `extract_failed` abort (A1)
- [X] T007 [US2] Add `--tasks-from <file>` to `main()`'s argparse in `scripts/poc_queue_runner.py`, and branch the task source INSIDE the existing `try/except (*MODEL_ERRORS, json.JSONDecodeError, OSError)` (~line 2668): `tasks = load_pinned_tasks(args.tasks_from, args.report, operator_patches) if args.tasks_from else extract_tasks(client, args.report, tracer, operator_patches)` — so a malformed/absent task file aborts cleanly as `extract_failed` (A1), NOT a raw traceback. Comment WHY: bypasses ONLY the MODEL task extraction; `--report` STAYS REQUIRED because the report-fix path (`extract_fix_for_finding`) and reconstruction still read it (A2/FR-004); everything downstream is unchanged; the shared tail still emits `extracted` so the funnel sees continuity (FR-005). For the `extract_start` event: keep it (proof_bench does not key on it) OR emit a `tasks_loaded` variant when pinned — either is fine, do not block on it (A3)

**Checkpoint**: US2 independently testable — T002–T004 pass; the harness proves a supplied finding.

---

## Phase 3: User Story 3 — the eval case is self-contained ground truth (Priority: P1)

**Goal**: the case carries a curated finding (loud on missing); `run_case` pins it via `--tasks-from`.

**Independent test**: a curated case loads and pins; a case missing a finding field fails loudly.

### Tests for User Story 3

- [X] T008 [P] [US3] Test in `tests/unit/test_proof_bench.py`: a manifest with `title`/`location`/`description` (+ existing fields) loads with the curated finding populated (FR-007)
- [X] T009 [P] [US3] Test in `tests/unit/test_proof_bench.py`: a manifest MISSING any of `title`/`location`/`description`, and one where a field is EMPTY, each raise `ProofBenchError` loudly — never a silent fallback (FR-008/SC-004)
- [X] T010 [P] [US3] Test in `tests/unit/test_proof_bench.py`: `run_case` (harness subprocess stubbed) writes a well-formed single-task file whose one task's `id` == `finding_id` and whose text == the manifest's, and the built argv contains `--tasks-from <that file>` and does NOT contain `--only` (FR-009/FR-010/SC-002)

### Implementation for User Story 3

- [X] T011 [US3] Add `title`, `location`, `description` to the `Case` dataclass in `scripts/proof_bench.py`
- [X] T012 [US3] In `load_case` in `scripts/proof_bench.py`, require `title`/`location`/`description` (empty treated as missing) — raise `ProofBenchError` when absent, the same loud discipline as the fix requirement (comment: never a silent fallback to nondeterministic model extraction)
- [X] T013 [US3] In `run_case` in `scripts/proof_bench.py`: before the N-run loop, write `[{"id": case.finding_id, "title": case.title, "location": case.location, "description": case.description}]` to a `tempfile` (external scratch, target material — cleaned up after the case); pass `--tasks-from <that>` in every run's argv and DROP `--only` (the file holds exactly the one task, whose id == finding_id == the `--fix-patch` id, so the fix attaches by construction — FR-010); comment WHY (pins id AND text across all N runs → prover input byte-identical, extraction variance removed — FR-009/SC-007)

**Checkpoint**: US3 independently testable — T008–T010 pass; the case pins its finding.

---

## Phase 4: Polish, dataset & cross-cutting

- [X] T014 Run `pytest tests/integration/test_poc_runner_loop.py tests/unit/test_proof_bench.py tests/unit/test_poc_queue_runner.py -q` — all pass offline; no model, container, or network (SC-006)
- [X] T015 Run the full suite `pytest -q` and confirm zero regressions — especially the existing `extract_tasks`-driven tests (`test_budget_stop` monkeypatches it) and every `_MUTVERIFY`/`run_case`/`load_case` test, since `extract_tasks` was refactored and `Case`/`run_case` changed (FR-006)
- [X] T016 [P] Verify the guards can fail by mutation: make `main()` ignore `--tasks-from` (always extract) → T002 FAILS; drop the `title` requirement in `load_case` → T009 FAILS; leave `--only` in `run_case`'s argv → T010's "no --only" assertion FAILS. Revert all three (SC-004)
- [ ] T017 Curate the 5 strata-bb case manifests (EXTERNAL, under `SR_PROOF_ROOT`, never committed): add `title`/`location`/`description` transcribed from the published report to each `case.json`, alongside the existing fields; confirm `proof_bench.load_dataset` loads all 5 with pinned findings — all EXTERNAL, never committed (FR-012)
- [X] T018 [P] Add a landing entry to `docs/roadmap.md` for spec 028: spec-026's strata-3 died at extraction (`only_ids_not_found`) — the harness re-ran nondeterministic model extraction every case-run; NOT a general bug (normal runs are self-consistent), only the eval's fixed-id-vs-fresh-extraction; fix = `--tasks-from` decouples extract from prove + the eval curates the finding and pins it (id AND text constant across runs), removing extraction variance from the number (the two-axis-separation of 026 US4); default operator path untouched
- [X] T019 Confirm no target material entered the repo: `git diff --stat` reviewed; every fixture finding in the new tests is invented; `pytest tests/architecture/test_no_target_material.py -q` passes

---

## Dependencies & Execution Order

```
Phase 1 Setup (T001)
   ├─> Phase 2 US2 harness (T002–T004 → T005 → T006 → T007)
   └─> Phase 3 US3 proof_bench (T008–T010 → T011 → T012 → T013)   ∥ independent of US2 (different file)
          └─> Phase 4 Polish (T014 → T015 → T016, T017, T018, T019)
```

- **US2 ∥ US3** — different files (`poc_queue_runner.py` vs `proof_bench.py`); land in either order.
- **US1 is emergent** — no code; validated by T010 (run_case pins via `--tasks-from`) + T002 (the
  harness honors it). The end-to-end "no case dies at extraction" (SC-001) is confirmed by the live
  re-run (operator step, out of scope here — the pieces are unit/integration-proved).
- **T005 (refactor) before T006/T007** — `load_pinned_tasks` and `extract_tasks` both call it.
- **T017 (curate manifests) depends on T011/T012** — the manifests must satisfy the new loader.

## Parallel Opportunities

- **T002–T004**, **T008–T010** — [P] within their groups (independent test functions).
- **US2 branch and US3 branch** proceed in parallel until Phase 4.
- **T016, T018** — [P]; different files (tests vs `docs/roadmap.md`).

## Implementation Strategy

**MVP = Phase 2 (US2) + Phase 3 (US3)** — together they ARE the feature: the harness accepts a pinned
task and the eval supplies one. Neither alone delivers US1 (a deterministic eval finding), so land both
before the live re-run.

**Then T017** curates the real dataset so the operator can re-run the baseline eval (a separate step)
with each finding pinned — the payoff that unblocks a clean proof-eval number.

**Total**: 20 tasks — 1 setup, 7 US2 (incl. the malformed-file clean-abort test), 6 US3, 6 polish (incl. dataset curation).
