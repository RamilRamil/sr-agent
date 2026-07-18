# Tasks: Make via_ir Compilation Viable in the Harness Sandbox

**Feature**: `027-sandbox-viair-memory` | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

**Scope**: ~3 changed lines in `scripts/poc_queue_runner.py` (a sandbox factory + the copy skip list),
one new architecture guard test, one unit assertion, a quickstart pre-step, and a LIVE calibration.
No `sr_agent/` change — the kernel sandbox and the secure agent are untouched.

**Tests ARE requested** — FR-011 makes the offline scoping/copy tests part of the feature.

**Split of validation**: the SCOPING (harness raised, secure agent not) and the COPY change are
offline/deterministic; the memory VALUE's sufficiency is inherently a LIVE operator step (offline
tests cannot run a memory-heavy build) — FR-012.

---

## Phase 1: Setup

- [X] T001 Create `tests/architecture/test_harness_sandbox_memory.py` with a docstring stating it guards FR-003/FR-010: the standalone harness raises its sandbox memory above the kernel default while the secure interactive agent does not; mirror the AST style of `test_harness_sandbox_only.py`

---

## Phase 2: User Story 1 — the harness can compile the target (Priority: P1)

**Goal**: the standalone harness builds its sandbox with an env-tunable, calibrated memory ceiling
higher than the kernel default; the secure agent and kernel default are untouched.

**Independent test**: `_harness_sandbox().memory_limit` parses to strictly more than the kernel default.

### Tests for User Story 1

- [X] T002 [P] [US1] Test in `tests/architecture/test_harness_sandbox_memory.py`: add a `_mem_bytes(s)` helper (parse "512m"/"6g" → bytes) and assert `_harness_sandbox().memory_limit` > `DockerSandbox().memory_limit` (the kernel default, still "512m") (FR-001/FR-002)
- [X] T003 [P] [US1] Test in `tests/architecture/test_harness_sandbox_memory.py`: `SR_SANDBOX_MEMORY` unset → the calibrated default applies; set via monkeypatch (e.g. "8g") → `_harness_sandbox()` honors it (FR-002)

### Implementation for User Story 1

- [X] T004 [US1] Add `_harness_sandbox()` to `scripts/poc_queue_runner.py`: return `DockerSandbox(memory_limit=os.environ.get("SR_SANDBOX_MEMORY", "6g"))`; comment WHY 6g (generous headroom over the killed 512m; via_ir on a mid-size target peaks low-GB; FR-004 confirmed by live calibration T012) and WHY env-tunable (different targets/hosts need different amounts)
- [X] T005 [US1] Replace the bare `sandbox = DockerSandbox()` at ~line 2668 in `scripts/poc_queue_runner.py` with `sandbox = _harness_sandbox()`; the same instance already flows to both `run_tests` and `mutation_verify`, so both get the raised ceiling

**Checkpoint**: US1 independently testable — T002/T003 pass; a cold via_ir build now has enough memory.

---

## Phase 3: User Story 2 — verified passes stop paying a full cold rebuild (Priority: P1)

**Goal**: the falsification copy carries the build cache so the patched rebuild is incremental, with
behavior otherwise identical.

**Independent test**: `_MUTVERIFY_COPY_SKIP` no longer excludes the forge cache.

### Tests for User Story 2

- [X] T006 [P] [US2] Test in `tests/unit/test_poc_queue_runner.py`: `_MUTVERIFY_COPY_SKIP` is the `shutil.ignore_patterns(...)` CALLABLE `fn(dirpath, names) -> set-to-ignore`; call it as `pqr._MUTVERIFY_COPY_SKIP("/proj", ["out","cache_forge",".git","node_modules","Foo.sol"])` and assert the returned ignore-set contains `.git`/`node_modules`, does NOT contain `cache_forge`/`out`, and does NOT contain the source file (FR-005)

### Implementation for User Story 2

- [X] T007 [US2] Change `_MUTVERIFY_COPY_SKIP` (~line 1682) in `scripts/poc_queue_runner.py` from `ignore_patterns("out", "cache_forge", ".git", "node_modules")` to `ignore_patterns(".git", "node_modules")`; comment WHY (forge's cache is content-keyed, so the fix's changed file is recompiled — a stale artifact is never served, FR-007 — turning a cold via_ir rebuild into seconds while `.git`/`node_modules` stay skipped as huge+irrelevant; the copy is still ephemeral, same-PoC, real-tree-untouched — FR-006)

**Checkpoint**: US2 independently testable — T006 passes; falsification rebuilds incrementally.

---

## Phase 4: User Story 3 — the raise cannot be silently lost or leaked (Priority: P1)

**Goal**: a guard pins the harness raised AND the secure agent unraised.

**Independent test**: flipping the harness back to bare `DockerSandbox()`, or raising a secure-agent
site, fails a test.

### Tests for User Story 3

- [X] T008 [P] [US3] Test in `tests/architecture/test_harness_sandbox_memory.py`: AST-inspect `sr_agent/packs/audit/pipeline.py` and `sr_agent/orchestrator/loop.py` — every `DockerSandbox(...)` construction there passes NO `memory_limit` keyword (the secure agent is unraised, FR-003/FR-010)
- [X] T009 [P] [US3] Test in `tests/architecture/test_harness_sandbox_memory.py`: `DockerSandbox().memory_limit == "512m"` — the kernel default is unchanged, so the secure-agent bare constructions get the low ceiling (FR-003)
- [X] T010 [US3] Mutation check in the docstring/comment: note that reverting T005 to bare `DockerSandbox()` fails T002, and adding a `memory_limit` to a secure-agent site fails T008 — the guard has teeth (SC-005)

**Checkpoint**: all three stories independently testable; the scoping is guarded both directions.

---

## Phase 5: Polish, live calibration & cross-cutting

- [X] T011 Run `pytest tests/architecture/test_harness_sandbox_memory.py tests/architecture/test_harness_sandbox_only.py tests/unit/test_poc_queue_runner.py -q` — all pass offline; the sandbox-only isolation guard is still green (no invariant moved, FR-009/SC-006)
- [X] T012 Run the full suite `pytest -q` and confirm zero regressions (this feature changes ~3 harness lines + adds tests; no existing behavior beyond the copy-skip should shift)
- [X] T013 **LIVE calibration + warm-cache confirmation (operator step, FR-008/FR-012/SC-001/SC-007)**: warm the target once with a host-side `forge build` (FR-008 — mounted cache warm, only the first build cold). **Step 1 (the memory PROOF, harness-free, no confound): raw `forge build` in the sandbox image at `--memory 512m` (expect SIGKILL) vs the chosen default (expect success).** This isolates the memory question — no extraction, no id-matching. Step 2 (end-to-end): re-run the finding that gave 2/2 SIGKILL (`--only 4` with its fix) and confirm it reaches the compiled stage — NOTE this step can hit `only_ids_not_found` if extraction emits a different id scheme (e.g. `H-04` vs `4`): that is the SEPARATE spec-026 id-scheme fragility, NOT a 027 failure — retry the run; do not read it as a memory failure. **FR-004 feedback loop: record the smallest surviving ceiling; if it is not `6g`, UPDATE the default in `_harness_sandbox` (T004) to the calibrated value.**
- [X] T014 [P] Verify the guards can fail by mutation: temporarily revert T005 to bare `DockerSandbox()` → T002 FAILS; temporarily add `memory_limit="6g"` to a `pipeline.py` construction → T008 FAILS; temporarily restore `"cache_forge"` to the skip list → T006 FAILS. Revert all three (SC-005)
- [X] T015 [P] Add a landing entry to `docs/roadmap.md` for spec 027: the first proof-eval run OOM-killed solc (via_ir vs 512m), diagnosed from the SIGKILL artifact (triangulated 3 ways); the harness sandbox now takes an env-tunable calibrated memory ceiling (secure agent unchanged, guarded); the falsification copy reuses the forge cache (cold full rebuild → incremental); NO security invariant moved (memory is a DoS knob)
- [X] T016 Confirm no target material entered the repo: `git diff --stat` reviewed; `pytest tests/architecture/test_no_target_material.py -q` passes (the changes are config + a copy-skip list; no target names)

---

## Dependencies & Execution Order

```
Phase 1 Setup (T001)
   ├─> Phase 2 US1 (T002, T003 → T004 → T005)
   ├─> Phase 3 US2 (T006 → T007)                     ∥ independent of US1 (different code region)
   └─> Phase 4 US3 (T008, T009 → T010)               depends on US1 (guards the raise T004/T005 introduces)
          └─> Phase 5 Polish (T011 → T012 → T013 → T014, T015, T016)
```

- **US1 and US2 are independent** — the memory raise (`_harness_sandbox`) and the copy-skip change are
  different regions of the same file; land in either order.
- **US3 depends on US1** — it guards the raise US1 introduces (and the secure-agent non-raise).
- **T013 (live calibration) depends on US1+US2 landed** — it validates the real behavior, and needs
  the sandbox factory in place.

## Parallel Opportunities

- **T002, T003** (US1 tests), **T008, T009** (US3 tests) — [P] within their groups.
- **T014, T015** — [P]; different files (tests vs `docs/roadmap.md`).
- **US1 branch and US2 branch** can proceed in parallel until Phase 5.

## Implementation Strategy

**MVP = Phase 1 + Phase 2 (US1)** — the correctness fix. Without the memory raise the harness compiles
nothing on a cold cache; this alone unblocks the eval.

**Increment 2 = Phase 3 (US2)** — the cache reuse. Makes a passing proof's falsification affordable
(seconds, not minutes) and removes the biggest residual cold-build OOM site.

**Increment 3 = Phase 4 (US3)** — the guard. Cheap, and it prevents a silent revert reintroducing the
exact OOM this feature fixes.

**Then T013 live calibration** confirms the memory VALUE on real hardware — the one thing offline
tests cannot.

**Total**: 16 tasks — 1 setup, 4 US1, 2 US2, 3 US3, 6 polish (incl. the live calibration).
