# Implementation Plan: Pin the Finding for the Proof-Eval

**Branch**: `028-pin-eval-finding` | **Date**: 2026-07-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/028-pin-eval-finding/spec.md`

## Summary

Spec 026's first proof-eval run had a case die at **extraction** (`only_ids_not_found`): the harness
re-runs model extraction every case-run, the model names findings nondeterministically, and the eval's
fixed id can't match a fresh extraction. Even normalizing ids leaves the finding's TEXT drifting run
to run — extraction variance in the number.

Fix, best-practice (separate the two axes; pin everything but the measured one):
1. **Harness `--tasks-from <file>`** — prove a supplied task list INSTEAD of model extraction;
   everything downstream (fix attachment, `--only`, drafting, compile, falsification) unchanged; the
   `extracted` event still fires so the funnel sees continuity. Default (no flag) untouched. A small
   decoupling of two welded stages, useful beyond the eval (reproducible re-runs, prover debugging).
2. **Curated finding in the eval case** — the manifest carries `title/location/description` (human
   ground truth, model-free), loaded loudly; `proof_bench.run_case` writes a one-task file and pins it
   with `--tasks-from`, so the finding's id AND text are identical across all C×N runs.

Grounded in [research.md](research.md): the task source is the only branch in `main()`; fix attachment
is shared via a small extracted helper.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: none new — stdlib `json`/`tempfile`

**Storage**: the task file is ephemeral external scratch (target material — never in the repo); case
manifests live under external `SR_PROOF_ROOT`

**Testing**: pytest, offline; harness subprocess + any model call are stubbed (never run in tests)

**Target Platform**: operator CLI (`scripts/poc_queue_runner.py`, `scripts/proof_bench.py`)

**Project Type**: single project — operator tooling; no kernel/pack change

**Performance Goals**: removes extraction variance from the eval number (SC-007); no perf target

**Constraints**: default operator path byte-identical (FR-006); the pinned path identical downstream
of extraction (FR-003); fully offline tests

**Scale/Scope**: ~15 changed/added lines in `poc_queue_runner.py` (a flag, a loader, a shared fix
helper), ~10 in `proof_bench.py` (3 Case fields, loud loader, run_case pins), tests, and 5 external
curated manifests. No `sr_agent/` change.

## Constitution Check

| Principle | Status | Rationale |
|---|---|---|
| **I. Secure-Kernel Trust Invariants** | ✅ PASS | No trust promotion, no new source type. The task file is operator-supplied data read by operator tooling; the finding it carries flows into the same prompt an extracted finding would. No kernel path touched. |
| **II. Human Authority** | ✅ PASS | Strengthens it, mildly: the eval's finding is now HUMAN-curated ground truth rather than a model's per-run guess. Findings are still confirmed only by a verified PoC. |
| **III. Kernel / Pack Separation** | ✅ PASS | Both changes are in `scripts/` operator tooling. No kernel or pack code; no new kernel→pack import. |
| **IV. Human-Gated Knowledge Promotion** | ✅ PASS | No knowledge-store writes. |
| **V. No Paid-API Dependency** | ✅ **STRENGTHENS** | The pinned path REMOVES a model call from the eval's per-run path (extraction is bypassed). The scoring path stays model-free; the default operator path still uses the model as before. |

**Gate result**: PASS on all five, V strengthened. No violations; Complexity Tracking empty.

## Project Structure

### Documentation (this feature)

```
specs/028-pin-eval-finding/
├── spec.md              # what & why (3 stories; "decouple + pin", not "fix a bug")
├── plan.md              # this file
├── research.md          # 4 decisions grounded in main()'s task seam
├── quickstart.md        # curate a case's finding, run the eval pinned, --tasks-from for debugging
├── tasks.md             # (/speckit-tasks)
└── checklists/
    └── requirements.md
```

No `data-model.md` (3 fields on an existing dataclass) or `contracts/` (the task-file JSON is the
existing `_extracted_tasks.json` shape). Omitted rather than stubbed.

### Source Code (repository root)

```
scripts/
├── poc_queue_runner.py          # MODIFIED
│   ├── _attach_fixes(tasks, report_text, operator_patches)   # NEW: extracted from extract_tasks' tail
│   ├── extract_tasks(...)       #   now calls _attach_fixes (behavior identical)
│   ├── load_pinned_tasks(path, report_path, operator_patches) # NEW: read file → _attach_fixes
│   ├── main() @ ~2669           #   if args.tasks_from → load_pinned_tasks, else extract_tasks
│   └── argparse                 #   NEW --tasks-from <file>
└── proof_bench.py               # MODIFIED
    ├── Case                     #   + title, location, description
    ├── load_case                #   require the curated finding (loud, like fix)
    └── run_case                 #   write one-task file, pass --tasks-from, drop --only

tests/
├── integration/test_poc_runner_loop.py   # EXTENDED — --tasks-from bypasses extract_tasks; default still extracts
└── unit/test_proof_bench.py              # EXTENDED — curated-finding loader + run_case pins via --tasks-from
```

**Structure Decision**: both files are in `scripts/` (operator tooling) — the kernel/pack is
untouched. `_attach_fixes` is extracted so the pinned and extracted paths share the exact fix logic
(no drift). The task file is written to a `tempfile` (external), consistent with how operator patches
and the mutation-verify copy handle target-derived scratch.

## Design

### PART 1 — `--tasks-from` (US1/US2)

`main()` today: `tasks = extract_tasks(...)` → emit `extracted` → write file → `--only` → prove.
Change: `tasks = load_pinned_tasks(args.tasks_from, args.report, operator_patches) if args.tasks_from
else extract_tasks(...)`. Everything after is unchanged, so:
- the `extracted` event fires with the loaded ids → the funnel sees the case reach `extracted`
  (FR-005; no false extraction-death);
- `--only`, drafting, compile, falsification are identical (FR-003).

`_attach_fixes(tasks, report_text, operator_patches)` — extracted from `extract_tasks`'s tail — sets
`fix = extract_fix_for_finding(report_text, task)` (FR-004, deterministic report path untouched) and
`fix_patch = operator_patches.get(id)` per task. Both `extract_tasks` and `load_pinned_tasks` call it,
so a pinned task gets its fixes exactly like an extracted one.

`load_pinned_tasks(path, report_path, operator_patches)`: read the JSON list, keep well-formed items
(id + title, mirroring `extract_tasks`), read the report for `_attach_fixes`, return the attached
tasks. Malformed/empty → loud (edge case).

### PART 2 — the curated case pins the finding (US3)

`Case` gains `title, location, description`. `load_case` requires them (and the existing
`finding_id`) — empty treated as missing → `ProofBenchError` (FR-007/FR-008), the same loud discipline
as the fix requirement.

`run_case`: before the N-run loop, write `[{"id": case.finding_id, "title": …, "location": …,
"description": …}]` to a `tempfile`; each run's argv gets `--tasks-from <that>` and `--fix-patch
<finding_id>=<fix>`, and NO `--only` (one task in the file). The temp file is removed after the case.
The id in the file == `finding_id` == the `--fix-patch` id, so the fix attaches by construction
(FR-010), and the same file across all N runs makes the prover's input byte-identical
(FR-009/SC-002/SC-007).

## Test Strategy

Offline, synthetic fixtures only (invented findings/task files — never target material).

`tests/integration/test_poc_runner_loop.py`:
- with `--tasks-from`, `main()` loads the file and does NOT call the model extractor (monkeypatch
  `extract_tasks` to raise → the run still succeeds via the file), and emits `extracted` with the
  file's ids;
- without `--tasks-from`, `extract_tasks` is still called (default path unchanged — FR-006);
- `_attach_fixes` attaches `fix`/`fix_patch` to a pinned task (FR-003/FR-004).

`tests/unit/test_proof_bench.py`:
- `load_case` requires `title`/`location`/`description`; absent OR empty → loud `ProofBenchError`
  (FR-008/SC-004);
- `run_case` (with its harness subprocess stubbed) writes a well-formed single-task file and the argv
  contains `--tasks-from` and no `--only` (FR-009); the one task's id == finding_id (FR-010).

The harness subprocess and any model call never run in tests (SC-006).

## Complexity Tracking

None. The Constitution Check passes on every principle with no deviation to justify.
