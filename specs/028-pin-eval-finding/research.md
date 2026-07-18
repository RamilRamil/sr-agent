# Research: Pin the Finding for the Proof-Eval (spec 028)

Grounded in the current code (`poc_queue_runner.main()`, `extract_tasks`, `proof_bench`) and the
spec-026 live-run artifact (`only_ids_not_found: ['3']`).

## Decision 1: `--tasks-from` swaps ONLY the task source; everything after is shared

**Finding**: `main()` obtains the task list, then does a fixed sequence regardless of source:
```python
tasks = extract_tasks(client, args.report, tracer, operator_patches)   # model
log({"event": "extracted", "count": len(tasks), "ids": [t["id"] for t in tasks]})
(poc_dir / "_extracted_tasks.json").write_text(...)
if args.extract_only: return
if args.only: ...                     # filter
# ... prove each
```
The `extracted` event, the `_extracted_tasks.json` write, `--only`, and the proving loop all run on
`tasks` regardless of where it came from.

**Decision**: add `--tasks-from <file>`. When set, `tasks = load_pinned_tasks(args.tasks_from,
args.report, operator_patches)` replaces the `extract_tasks(...)` call. Nothing after changes — the
`extracted` event fires with the loaded ids (FR-005), the file is (re)written, `--only`/proving run
unchanged (FR-003). Default (no flag) is byte-for-byte the current path (FR-006).

**Rationale**: the seam is exactly one line (the task source). Sharing the tail keeps the pinned path
identical to the extracted one downstream — which is the whole point (the eval measures proving, which
is the tail). The `extracted` event firing means `proof_bench._stage_of` sees the finding_id in
`extracted.ids` → the case reaches the `extracted` stage, never a false extraction-death (FR-005,
edge case).

## Decision 2: fix attachment is shared, so a pinned task still gets its fixes

**Finding**: `extract_tasks` doesn't just call the model — it then ATTACHES two fixes per task:
```python
finding["fix"] = extract_fix_for_finding(report, finding)        # deterministic, from the report
finding["fix_patch"] = operator_patches.get(finding["id"])       # from --fix-patch
```
A pinned task must get the same, or falsification breaks (no fix ⇒ `passed_unchecked`).

**Decision**: extract a helper `_attach_fixes(tasks, report_text, operator_patches) -> tasks` from
`extract_tasks`'s tail, and call it from BOTH `extract_tasks` (after the model) and `load_pinned_tasks`
(after reading the file). `load_pinned_tasks` reads the JSON task list, keeps only well-formed items
(id + title, like `extract_tasks`), and runs `_attach_fixes`. The report is still read for
`extract_fix_for_finding` (FR-004 — the deterministic report-fix path is untouched; only the MODEL
extraction is bypassed).

**Rationale**: DRY and correctness — the pinned path and the extracted path share the exact fix
attachment, so a pinned finding behaves identically (FR-003). Duplicating the 3 lines would risk
drift.

**Alternatives considered**: require the task file to already carry `fix`/`fix_patch` — rejected: the
report-fix is deterministic and belongs to the harness, not the case file; and `fix_patch` comes from
the `--fix-patch` CLI, resolved at runtime. Keeping attachment in the harness keeps the case file to
the finding only.

## Decision 3: the proof-eval case carries the curated finding; `run_case` pins it

**Finding**: `proof_bench.Case` has `case_id, target_path, report_path, finding_id, fix_path`.
`run_case` builds argv with `--only <finding_id> --fix-patch <finding_id>=<fix>` and relies on
extraction to produce a matching task — the fragile step.

**Decision**:
- `Case` gains `title, location, description`. `load_case` requires them (loud, like the fix
  requirement — FR-007/FR-008); empty is treated as missing (edge case).
- `run_case` writes a single-task file `[{"id": finding_id, "title", "location", "description"}]` to a
  temp path (once per case, before the N runs), and passes `--tasks-from <that>` + `--fix-patch
  <finding_id>=<fix>` — and DROPS `--only` (the file already contains exactly the one task). The temp
  file is cleaned up after the case's runs.

**Rationale**: the pinned task's id equals `finding_id` equals the `--fix-patch` id, so the fix
attaches by construction — no fresh match (FR-010). The finding's id AND text are identical across all
N runs (the same file), so the prover's input is byte-identical (FR-009/SC-002) and extraction
variance is gone from the number (SC-007). `--only` is redundant with a one-task file, so dropping it
is cleaner and avoids a second id-coupling.

## Decision 4: the task file is target material — external, temp, never committed

**Decision**: `run_case` writes the single-task file to a `tempfile` dir (outside the repo), passes
its path, and removes it after the case. The 5 reference case manifests (now carrying curated
findings) live under the external `SR_PROOF_ROOT`, never committed (FR-012).

**Rationale**: the task file carries the target's finding title/location — target material (memory
`feedback_no_target_code_in_agent`). It is ephemeral scratch, like the operator patches and the
mutation-verify copy. Tests use SYNTHETIC invented findings only.

## Test seam (offline, deterministic)

- **Harness** (`tests/integration/test_poc_runner_loop.py` or a small new unit): with `--tasks-from`,
  `main()` loads the file and does NOT call `extract_tasks` (monkeypatch it to explode), emits
  `extracted` with the file's ids, and proceeds; without it, `extract_tasks` is still called (default
  unchanged). `_attach_fixes` attaches `fix`/`fix_patch` to a pinned task (FR-003/FR-004).
- **proof_bench** (`tests/unit/test_proof_bench.py`): `load_case` requires
  `title`/`location`/`description`, loud on absent/empty; `run_case` writes a well-formed single-task
  file and includes `--tasks-from` (and not `--only`) in the argv — the harness subprocess is stubbed
  (never run). All synthetic, no model/container/network.
