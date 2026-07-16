# Tasks: Ground-Truth Benchmark for Vulnerability Discovery

**Input**: Design documents from `specs/023-discovery-benchmark-rig/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/bench-rig.md

**Tests**: INCLUDED — spec mandates them (FR-014). The matcher's anti-inflation property is the integrity core and is tested BEFORE it is written.

**Organization**: by user story. All code lands in `scripts/bench.py` + one test file + docs.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different file, no dependency on an incomplete task)
- Paths are repo-root-relative

---

## Phase 1: Foundational — entities + loader

**Purpose**: the dataset contract and its guards; everything else scores what this loads.

- [X] T001 Create `scripts/bench.py` with module docstring (operator measuring rig; dataset EXTERNAL and never committed; scoring is pure — no model, no network; lives in `scripts/` because the kernel may not import the audit pack). Add `BenchError(Exception)` and dataclasses per data-model.md: `GroundTruth`(finding_id, bastet_tag: BastetTag, location, function_name, severity), `Candidate`(finding_id, bastet_tag: BastetTag|None, location, function_name, severity), `Case`(case_id, target_path|repo_url+commit, report_path|None, truth: list[GroundTruth]). Import `BastetTag` from `sr_agent.packs.audit.finding`. Stdlib only otherwise.
- [X] T002 Add `load_case(case_dir) -> Case` and `load_dataset(root) -> list[Case]`: root from `--root` or `SR_BENCH_ROOT`; resolve and REJECT (`BenchError`) any root/case/target inside the agent repo (mirror the `_AGENT_ROOT in resolved.parents` guard from `frontend/backend/sessions.py`); parse `case.json` (exactly one of `target_path`/`repo_url`) and `labels.json`; every label's `bastet_tag` MUST parse to a `BastetTag` else `BenchError` naming the bad value (loud, NEVER a silent skip — a skipped label would quietly shrink the recall denominator).

**Checkpoint**: a synthetic case in a temp dir loads; an in-repo root or a bad tag raises `BenchError`.

---

## Phase 2: User Story 3 — honest matching (Priority: P1) 🎯 integrity core

**Goal**: a number that cannot inflate itself.

**Independent Test**: near-misses (right place/wrong class, right class/wrong place, text-similar only, untagged) are never credited; recall doesn't move.

### Tests for US3 (write FIRST)

- [X] T003 [P] [US3] Create `tests/unit/test_bench_rig.py`. Build the SYNTHETIC case **in `tmp_path`** (never a checked-in fixture — satisfies the external-root guard and keeps finding-shaped data out of the repo). Assert the anti-inflation properties of `match_findings`: same location+same tag → `matched`; same location+different tag → NOT matched, `needs_review(reason="tag_mismatch")`; same tag+different location → NOT matched, `needs_review(reason="location_mismatch")`; a candidate whose only similarity is free-text/notes → never matched; `bastet_tag=None` candidate → never matched; unmatched truth → `missed`; two candidates onto one truth → credited once, surplus → `spurious`. In every negative case assert recall is unchanged. Also: loader guards (in-repo root → `BenchError`; unknown tag → `BenchError`).

### Implementation for US3

- [X] T004 [US3] In `scripts/bench.py`: `normalize_location(location, function_name) -> tuple[str, str]` (strip path → basename or contract name, lowercase both) and `match_findings(produced, truth) -> MatchResult` implementing the rule from data-model.md EXACTLY: credit iff normalized location equal AND `bastet_tag` equal; else classify into `needs_review` / `spurious` / `missed`; many→one credited once. Deterministic ordering (sort by finding_id) so runs are byte-identical. Add a comment tying this to `_poc_defects`: a permissive matcher would inflate recall the way "it compiled" once inflated PoC quality.

**Checkpoint**: `pytest tests/unit/test_bench_rig.py -q` green; no near-miss earns recall.

---

## Phase 3: User Story 1 — the scorecard (Priority: P1) 🎯 MVP

**Goal**: per-class recall + named missed list, deterministic, written outside the repo.

### Tests for US1

- [X] T005 [P] [US1] In `tests/unit/test_bench_rig.py`: per-tag recall arithmetic (2 truth of tag X, 1 matched → `per_tag_recall["X"] == 0.5`; a tag with NO truth findings → `n/a`/`None`, never `0`); `recall = |matched|/|truth|`, `precision = |matched|/|produced|` with `needs_review`+`spurious` in the precision denominator; 100 spurious candidates → recall unchanged, precision collapses (volume can't buy recall); every unmatched truth appears in `missed_named` with id+tag+location; a detector returning `[]` → recall 0, all truth missed, no crash; re-running is byte-identical.

### Implementation for US1

- [X] T006 [US1] Add `score(case, detector_name, match, produced_n) -> Scorecard` (recall, precision, `per_tag_recall` with `None` for tags absent from truth, `missed_named`, counts) — pure arithmetic, no model, no clock/random in the output.
- [X] T007 [US1] Add report emission: a human-readable stdout summary (recall/precision, a per-tag table, the NAMED missed list) and a machine-readable `<root>/results/<case_id>.<detector>.json`. Results are written under the EXTERNAL bench root only — never inside the repo.

**Checkpoint**: a fake detector over the synthetic case yields a full, reproducible scorecard.

---

## Phase 4: User Story 2 — pluggable detectors + honest baselines (Priority: P1)

**Goal**: one ruler for today's floor and every future approach.

### Tests for US2

- [X] T008 [P] [US2] In `tests/unit/test_bench_rig.py`: registering a fake detector in `DETECTORS` and running it needs no change to matcher/scorer/dataset; the `heuristic` detector on a synthetic contract containing `tx.origin` emits a candidate tagged `incorrect-access-control`; on a synthetic contract with an external `.call` followed by a state write it emits a `reentrancy` candidate (C2); on a synthetic contract using only `assembly`/`.transfer(` (flags with no honest tag) it emits NOTHING; and on a business-logic-only contract (no red-flag substrings at all) it emits NOTHING — the honest floor.

### Implementation for US2

- [X] T009 [US2] Add `DETECTORS: dict[str, Detector]` (`Detector = Callable[[Case], list[Candidate]]`) and the `heuristic` detector.
  - **C1 (must):** do NOT use `run_stage1` — it returns only `priority_targets: ["file:function"]` and DISCARDS the flags, so a tag can't be derived from it. Use the pack's lower-level functions directly, per Solidity file: `extract_functions(source) -> [(name, body, line)]` then `score_function(body) -> (score, flags)` (these DO return the flags). Stage 1 itself is not modified.
  - Map ONLY flags with an honest `BastetTag`: `tx_origin_auth → incorrect_access_control`, `delegatecall → delegatecall_injection`, `timestamp_dependence → timestamp_dependence`, and **C2:** `external_call_before_state_write → reentrancy` (this synthesized flag is a real reentrancy SHAPE — external call followed by a state write — not a substring; omitting it would understate the floor, which is self-deception in the other direction).
  - Flags with NO defensible tag (`inline_assembly`, `native_transfer`, `native_send`, `low_level_call`, `low_level_call_value`, `selfdestruct`, `weak_randomness` — the taxonomy has no randomness tag) emit NOTHING; inventing a tag to score points is the exact self-deception this spec exists to prevent. Document the 4-entry mapping table in a comment.
- [X] T010 [US2] Add the `llm` detector: for each target file, call the pack's `analyze_target(client, target, source)` (it already DATA-wraps the code and returns the label shape, parsed via `adapt_findings` with enum-enforced tags) using a client from spec 022's `build_generation_client(provider, model, host, timeout)`. No prefiltering of targets (FR-009). Errors from one target are logged and skipped, not fatal.
- [X] T011 [US2] Add the argparse CLI: `run --detector {heuristic|llm} [--case ID] [--provider {local|openrouter|gemini}] [--root PATH]` and `cases` (list loaded cases + truth counts). `BenchError` → clear message + non-zero exit, no traceback.

**Checkpoint**: `python scripts/bench.py run --detector heuristic` scores every case; a new detector registers by name alone.

---

## Phase 5: Polish & Cross-Cutting

- [X] T012 [P] Update `docs/roadmap.md`: spec 023 landing — the project could prove findings (2515-LOC harness) but not measure discovery (~514 LOC, no ground truth); this rig makes it measurable. Record the design constraints and WHY (dataset external per `feedback_no_target_code_in_agent`; rig in `scripts/` because kernel↛pack; conservative structural matching = the `_poc_defects` lesson applied to measurement; human-curated labels or we measure a model against itself; no prefiltering). Note Stage 1 emits no findings/tags — the `heuristic` floor maps only 3 of 10 red flags honestly and is expected to score ~0 on business logic. Next: the instrument exists to measure a real detector (taxonomy sweep / invariant+fuzzer).
- [X] T013 Final gate: full suite offline (no `SR_BENCH_ROOT`, no keys, no network) `pytest -q` green, zero regressions; `ruff check scripts/bench.py tests/unit/test_bench_rig.py` clean; confirm no dataset/target-shaped data was added to the repo (`git status` clean of such files).

---

## Dependencies & Execution Order

- **Foundational (T001-T002)** → entities + loader; blocks everything.
- **US3 (T003-T004)** → the matcher; blocks scoring. Tests first (integrity core).
- **US1 (T005-T007)** depends on US3 (needs `MatchResult`).
- **US2 (T008-T011)** depends on T001-T002 (Case) and, for the CLI, on US1's scorer/report.
- **Polish (T012-T013)** last.

## Parallel Opportunities

- T003 / T005 / T008 are `[P]` groups in the same new test file — write together, they cover independent properties.
- T012 (docs) `[P]` once behavior is settled.

## Implementation Strategy

MVP = Foundational + US3 + US1 (a trustworthy scorecard driven by a fake detector). US2 then supplies the real baselines: `heuristic` (the honest ~0 floor) and `llm` (what a model finds unaided). The matcher's anti-inflation tests land BEFORE the matcher so the measuring stick can't be quietly bent.

**Total tasks**: 13 (Foundational 2, US3 2, US1 3, US2 4, Polish 2).
