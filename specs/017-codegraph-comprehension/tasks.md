# Tasks: Code-Comprehension Graph for Our Own Codebases

**Input**: Design documents from `specs/017-codegraph-comprehension/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/codegraph-cli.md

**Tests**: INCLUDED — the spec mandates them (FR-011 offline fixture query tests, FR-012 isolation guard test, US3 independent test).

**Organization**: by user story. All code lives in `scripts/codegraph.py` (+ tests + fixture); no changes under `sr_agent/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different file, no dependency on an incomplete task)
- Single project: paths are repo-root-relative

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: skeleton file, fixture, and ignore entry that everything else builds on.

- [X] T001 Create `scripts/codegraph.py` with module docstring (states: dev tool, offline, no LLM, not imported by kernel), stdlib imports only (`json`, `pathlib`, `subprocess`, `collections`, `argparse`, `sys`, `shutil` — add others only when actually used; do NOT import `os` unless needed), and typed exceptions `CodeGraphFormatError` and `GraphifyMissing`.
- [X] T002 [P] Create the checked-in fixture `tests/fixtures/codegraph_sample.json` — a node-link map of the two-file sample (nodes: `main`, `main_run`, `util`, `util_add`, `util_calc`, `util_calc_total`; edges: `main→main_run contains`, `main→util imports_from`, `main→util_add imports`, `main→util_calc imports`, `main_run→util_add calls`, `main_run→util_calc calls`, `util→util_add contains`, `util→util_calc contains`, `util_calc_total→util_add calls`, `util_calc→util_calc_total method`), each with `source_file`/`source_location`/`confidence=EXTRACTED`, matching the shape in research.md.
- [X] T003 [P] Add `graphify-out/` to `.gitignore` (ignore generated map output for any mapped repo root).

**Checkpoint**: file imports cleanly; fixture is valid JSON.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the in-memory `CodeGraph` model + validated loader — every query depends on it.

- [X] T004 In `scripts/codegraph.py`, add `CodeNode` and `CodeEdge` dataclasses per data-model.md (`CodeNode`: id, label, file, line, kind, origin; `CodeEdge`: source, target, relation, confidence, file, line). Parse `source_location` `"L<n>"` → int (`None` if absent).
- [X] T005 Add `CodeGraph` with `@classmethod load(path)` that reads `graph.json`, validates top-level `nodes`/`links` are lists and each node has `id` / each edge has `source`,`target`,`relation` (raise `CodeGraphFormatError` naming the missing key/record on failure), and builds `nodes` (id→CodeNode), `out` (id→[edge]), `in_` (id→[edge]) indexes. Tolerate unknown `relation`/`confidence` values.
- [X] T006 Add a deterministic sort helper (`(file, line, id)`) used by every query for stable ordering (SC-004).

**Checkpoint**: `CodeGraph.load(fixture)` returns a populated graph; malformed input raises `CodeGraphFormatError`.

---

## Phase 3: User Story 1 — Structural questions over the map (Priority: P1) 🎯 MVP

**Goal**: answer define / neighbors / callers / callees / dependencies / path / module-summary over a built map, LLM-free.

**Independent Test**: over `tests/fixtures/codegraph_sample.json`, `callers("util_add")` returns exactly the top-level `main_run` and the method `util_calc_total`; `path("main_run","util_add")` returns a chain; missing name → `[]`.

### Tests for US1 (write first)

- [X] T007 [P] [US1] Create `tests/unit/test_codegraph_query.py` loading the fixture and asserting: `find("add")` resolves to `util_add`; `find("nope")==[]`; `callers("util_add")` == {`main_run`,`util_calc_total`} with `relation=="calls"` and `confidence` surfaced; `callees("main_run")` includes `util_add`; `dependencies("main")` returns the `imports`/`imports_from` edges; `neighbors("util_calc")` includes both in and out edges; `path("main_run","util_add")` is a non-empty ordered chain and `path` between unconnected nodes is `[]`; `module_summary("util")` lists its `contains`/`method` children. Assert deterministic ordering by running a query twice and comparing.

### Implementation for US1

- [X] T008 [US1] Implement `find(name)` (match by id, exact label, or label stripped of `()`/`.`) and `define(name)` (find → node locations) in `scripts/codegraph.py`.
- [X] T009 [US1] Implement `neighbors(id)`, `callers(id)` (inbound `calls`), `callees(id)` (outbound `calls`), `dependencies(id)` (outbound `imports`/`imports_from`) — all returning sorted `CodeEdge` lists.
- [X] T010 [US1] Implement `path(a, b)` as unweighted BFS over `out` edges returning the shortest ordered `CodeEdge` chain (`[]` if none), and `module_summary(id)` returning children (`contains`/`method`) + inbound/outbound counts.
- [X] T011 [US1] Add the `argparse` CLI query subcommands (`define`, `callers`, `callees`, `deps`, `neighbors`, `path`, `module`) with `--graph` override; format each element as `label (file:line)` and each relationship with `relation` + `confidence`; `not found`/`no path` print to stderr and exit non-zero; missing/malformed graph prints an actionable message (point at `build`) without a traceback.

**Checkpoint**: `pytest tests/unit/test_codegraph_query.py -q` passes offline; CLI query commands work against the fixture via `--graph`.

---

## Phase 4: User Story 2 — Build/refresh the map offline (Priority: P2)

**Goal**: generate the map for any of our repo roots via graphify, offline, non-destructively, degrading cleanly when graphify is absent.

**Independent Test**: `build_graph(sample_dir)` with all provider creds unset produces a `graph.json`; with graphify absent it raises `GraphifyMissing`.

### Implementation for US2

- [X] T012 [US2] Implement `build_graph(root)` in `scripts/codegraph.py`: run `graphify extract <root> --code-only --no-viz` via `subprocess.run` (inherit env), return the `<root>/graphify-out/graph.json` path; raise `GraphifyMissing` (not raw `FileNotFoundError`) when the CLI is not on PATH; surface a non-zero graphify exit with its stderr. (`--code-only` required — the T018 smoke showed plain `--no-viz` demands an LLM key on repos that contain docs.)
- [X] T013 [US2] Add the CLI `build [ROOT]` subcommand (default ROOT = repo root): on `GraphifyMissing` print the `uv tool install graphifyy` line and exit non-zero without a traceback; on success print map path + node/edge counts.
- [X] T014 [P] [US2] Add `tests/unit/test_codegraph_build.py`: assert `build_graph` raises `GraphifyMissing` when the `graphify` executable is not resolvable (monkeypatch PATH / shutil.which), and that the CLI `build` handler turns it into a clean message + non-zero exit (no traceback). No real graphify invocation, no network. **Note (C1): the POSITIVE offline-build path (SC-002 — graphify actually builds a map with all provider creds unset) is verification-only — it cannot run in offline CI because graphify is intentionally not a dependency; it is covered by this session's hands-on verification and the T018 quickstart smoke, not by an automated test here.**

**Checkpoint**: build path is covered offline; graceful-absence verified without installing graphify.

---

## Phase 5: User Story 3 — Prove kernel isolation (Priority: P1)

**Goal**: a machine-checkable guarantee that this stays a dev tool — kernel never imports it, query path has no paid/network/graphify import, core suite passes with graphify absent.

**Independent Test**: guard test passes now and fails if a `sr_agent/**` file imports `scripts.codegraph` or if the query path gains a forbidden import.

### Tests for US3

- [X] T015 [US3] Create `tests/architecture/test_codegraph_isolation.py` (AST-based, mirroring `tests/architecture/test_kernel_pack_boundary.py`): assert no file under `sr_agent/**` imports `scripts.codegraph` (kernel or pack); and assert `scripts/codegraph.py`'s own imports exclude `requests`, `anthropic`, `socket`, `urllib`, `http`, and `graphify` (graphify is only ever a subprocess string, never an import) — proving no network / no paid API / no hard graphify dependency in the query path.
- [X] T016 [US3] Run the full suite offline with graphify uninstalled (`pytest -q`) and confirm zero regressions and that the two new suites pass (SC-003, SC-005).

**Checkpoint**: isolation guaranteed by test; whole suite green offline.

---

## Phase 6: Polish & Cross-Cutting

- [X] T017 [P] Update `docs/roadmap.md`: add the spec 017 landing entry recording the integration, the offline/no-credential verification, and the explicit boundaries (graphify can't parse Solidity → SymbolIndex still owns target grounding; the map is never model grounding / never in the trust hierarchy).
- [X] T018 [P] Validate `quickstart.md` commands against the built agent-repo map (manual smoke: `build`, then `callers _fix_scaffold_base`, `path _process_finding revert_hints`) and correct any command/flag drift.
- [X] T019 Final gate: `pytest -q` fully offline (graphify absent) is green; confirm `scripts/codegraph.py` is ruff-clean (`ruff check scripts/codegraph.py`).

---

## Dependencies & Execution Order

- **Setup (T001-T003)** → blocks everything.
- **Foundational (T004-T006)** → blocks all queries (US1) and is used by build output shape.
- **US1 (T007-T011)** depends on Foundational. This is the MVP.
- **US2 (T012-T014)** depends only on Setup (skeleton + exceptions from T001); independent of US1 queries — can proceed in parallel with US1 after Foundational.
- **US3 (T015-T016)** depends on the module existing (T001) and is most meaningful once US1/US2 code is present; T016 is the offline full-suite gate.
- **Polish (T017-T019)** last.

## Parallel Opportunities

- T002 and T003 in parallel (fixture vs gitignore).
- T007 (US1 test) parallel with T014 (US2 test) — different files.
- T017 and T018 in parallel (docs vs quickstart smoke).
- US1 (T008-T011) and US2 (T012-T013) implementation can overlap once Foundational is done (same file `scripts/codegraph.py` — coordinate edits, so treat as sequential within the file though logically independent).

## Implementation Strategy

MVP = Phase 1 + Phase 2 + US1 (T001-T011): a developer can query an existing map. US2 adds building it; US3 nails the security boundary; Polish documents it. Each user story is independently testable per its Independent Test above.

**Total tasks**: 19 (Setup 3, Foundational 3, US1 5, US2 3, US3 2, Polish 3).
