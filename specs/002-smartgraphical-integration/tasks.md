# Tasks: SmartGraphical Integration

**Feature**: SmartGraphical as a third deterministic analysis engine (logic findings + structural graph)
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Branch**: `002-smartgraphical-integration`

**Tests**: Included — they directly validate the security invariants (hypothesis status, provenance) and the mapping/graph logic. Pattern: fixture-based unit tests (no SmartGraphical needed) + an auto-skipping live integration test (like `test_slither_live.py`).

---

## Phase 1: Setup

- [X] T001 [P] Create `tests/fixtures/smartgraphical/` with `sample_findings.json` (a real `sg_cli ... all auditor json` output containing a logic finding + an evidence with function/line) and `sample_graph.json` (a `{nodes, edges}` payload with `state_to_function_read/write`, `function_to_function`, and a `cross_type_call` edge)
- [X] T002 [P] Add `examples/inheritance-vault/` — two `.sol` files where a child contract's function and an inherited parent function write the same state variable (US2 fixture; minimal, compiles under ^0.8.20)

---

## Phase 2: Foundational (Blocking Prerequisites)

- [X] T003 Create `sr_agent/tools/smartgraphical.py` — `SmartGraphicalError`, `SGFinding` dataclass (rule_id, task_id, title, category, confidence, message, remediation_hint, function, line), `SG_CONFIDENCE_TO_SEVERITY` (high/medium/low), and `SG_RULE_TO_TAG` lookup (per research.md R3; unmapped → None)

**Checkpoint**: shared module + mappings exist; user stories can build in parallel.

---

## Phase 3: User Story 1 — Logic-level findings from a third engine (Priority: P1) 🎯 MVP

**Goal**: Run SmartGraphical on each contract; ingest its logic findings as `tool_output`, attributed to the `smartgraphical` engine, in the report alongside Slither/Mythril.

**Independent Test**: Run an audit on a contract with a logic flaw the others miss; assert a SmartGraphical-attributed `tool_output` finding appears in the report.

- [X] T004 [P] [US1] Implement `parse_sg_findings(stdout) -> list[SGFinding]` in `sr_agent/tools/smartgraphical.py` — tolerant JSON parse (extracts `findings[]`, first evidence → function/line); empty/garbled → `[]`; raises `SmartGraphicalError` only on non-JSON non-empty text
- [X] T005 [P] [US1] Implement `sg_to_findings(sg_findings, file_rel) -> list[Finding]` — severity from confidence, bastet_tag via `SG_RULE_TO_TAG`, location `file_rel:line`, function_name from evidence (mirrors `slither_to_findings`)
- [X] T006 [US1] Implement `run_smartgraphical(target, audit_root, runner, timeout_s=120)` — subprocess CLI (and Docker `smartgraphical:local` option) producing JSON; parse via `parse_sg_findings`; raise `SmartGraphicalError`/`SandboxUnavailable` when unavailable
- [X] T007 [US1] Extend `sr_agent/orchestrator/pipeline.py::_run_static_analysis` — also run SmartGraphical per file (best-effort, auto-skip on any error), writing findings to memory as `source_type=tool_output` with payload `engine="smartgraphical"` + `rule_id`/`category`/`confidence`/notes
- [X] T008 [US1] Add `engine` attribution across finding-writing paths — set `engine="slither"` in the Slither pass, `engine="model"` in `run_stage2_local`/relay ingest; extend `sr_agent/io/report.py::_render_finding` to show an `Engine:` line when present
- [X] T009 [P] [US1] Unit tests `tests/unit/test_smartgraphical.py` — `parse_sg_findings` (fixture + garbage + empty), `sg_to_findings` (severity/tag/location mapping, unmapped rule → None tag), confidence→severity table
- [X] T010 [US1] Live integration test `tests/integration/test_smartgraphical_live.py` — auto-skip if SmartGraphical CLI/Docker unavailable; on the example contract assert ≥1 SmartGraphical finding with engine attribution (SC-001)

**Checkpoint**: SC-001 — SmartGraphical contributes a logic finding the other engines miss, attributed in the report.

---

## Phase 4: User Story 2 — Accurate interference graph (Priority: P2)

**Goal**: Build the State Interference Graph from SmartGraphical's structural graph (accurate read/write, inheritance, multi-file) so Stage 3 combines only genuinely interacting findings.

**Independent Test**: On the inheritance example, assert the SG-built graph marks the child/parent functions sharing state as interacting and Stage 3 links their findings — a case the regex SIG misses.

- [X] T011 [US2] Implement `parse_sg_graph(stdout_or_payload) -> dict` and `build_sig_from_smartgraphical(graph) -> StateInterferenceGraph` in `sr_agent/planner/sig.py` — reads/writes from `state_to_function_read/write` (+ `cross_type_state_*`), adjacency from `function_to_function`/`cross_type_call`, external-call flags from system/object edges; same `interferes()`/`can_reenter()`
- [X] T012 [US2] Extend `sr_agent/orchestrator/pipeline.py::_finish` — obtain SmartGraphical's graph (per-file or bundle) and build the SIG from it when available; fall back to `build_sig` otherwise; pass the chosen SIG to `run_stage3`
- [X] T013 [P] [US2] Unit tests `tests/unit/test_sig.py` (extend) — `build_sig_from_smartgraphical` on `sample_graph.json`: read/write sets correct, `function_to_function`/`cross_type_call` adjacency, inheritance functions interfere
- [X] T014 [US2] Integration test on `examples/inheritance-vault/` — child+parent functions sharing state are linked in Stage 3 `combined_with` via the SG graph (auto-skip live SG; or use a stored graph fixture for determinism) (SC-002)

**Checkpoint**: SC-002 — cross-inheritance interference detected and combined, beating the regex graph.

---

## Phase 5: User Story 3 — Findings remain unconfirmed hypotheses (Priority: P3)

**Goal**: Pin the security invariant — SmartGraphical findings are `tool_output` hypotheses, sanitized, never auto-confirmed; only PoC confirms.

**Independent Test**: Ingest a SmartGraphical finding; assert provenance `tool_output`, status unconfirmed, message sanitized, no privileged status set.

- [X] T015 [P] [US3] Tests `tests/integration/test_smartgraphical_invariant.py` — a SmartGraphical finding (incl. one with a manipulative-looking message + zero-width char) ingests as `tool_output`, status not `confirmed`, notes sanitized (flags present), and a relayed-style `verified_safe` cannot ride in via the engine path (SC-004)
- [X] T016 [US3] Verify report engine-attribution is present for every finding across all engines (Slither/Mythril/SmartGraphical/model) — assertion test over a mixed report (SC-005)

**Checkpoint**: SC-004/SC-005 — hypothesis invariant + full provenance verified.

---

## Phase 6: Polish & Cross-Cutting

- [X] T017 [P] Add `--no-smartgraphical` flag to `sr-agent audit` (and a `run_smartgraphical` pipeline param) so the engine can be disabled; default keeps existing behavior working (FR-010, SC-003)
- [X] T018 [P] Update `docs`/README + `.env.example` (SmartGraphical path / image name) and the quickstart verification commands
- [X] T019 Run the full suite (`pytest tests/` excluding slow mythril) + a live `sr-agent audit` smoke with all engines; confirm SmartGraphical findings + engine attribution in the report

---

## Dependencies & Order

- **Phase 1 (Setup)** and **Phase 2 (Foundational)** block everything.
- **US1 (P1)** depends on Phase 2 — this is the MVP.
- **US2 (P2)** depends on Phase 2 (sig.py seam) — independent of US1; can run in parallel after Foundational.
- **US3 (P3)** depends on US1 (needs the ingest path to assert over).
- **Polish** depends on US1–US3.

## Parallel Opportunities

- T001, T002 (fixtures) in parallel.
- After T003: T004, T005, T009 [US1] and T011, T013 [US2] are largely parallel (different functions/files).
- US1 and US2 are independent vertical slices once Foundational is done.

## MVP Scope

**US1 alone** (Phases 1–3) is a shippable MVP: the audit gains a whole new class of logic findings,
attributed and stored as verifiable hypotheses. US2 (graph accuracy) and US3 (invariant proof)
layer on top.
