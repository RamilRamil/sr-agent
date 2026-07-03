# Tasks: Kernel / Capability-Pack Boundary

**Input**: Design documents from `/specs/004-kernel-pack-boundary/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R12), data-model.md, contracts/{pack-interface,boundary-check,hostile-pack}.md

**Tests**: INCLUDED — the boundary check (SC-001) and the hostile-pack suite (US2/SC-003) are the feature's primary deliverables, and Constitution §Development Workflow mandates test-first for security-critical behavior. The existing suite is the behavior-preservation oracle.

**Organization**: By user story. US1 and US2 are **co-P1** (Constitution III makes "a pack cannot lower a guardrail" a mandatory tested property). Per the agreed sequencing, **US2 is front-loaded** so the security property + a green suite land early, and the boundary check runs as an **N→0 ratchet** with a safe stopping point after each relocation.

**Strategy note (behavior-preserving)**: Assemble a working `AUDIT_PACK` early (sourcing the *current* audit definitions), invert the kernel to consume it, THEN relocate definitions into `sr_agent/packs/audit/`, **inverting each kernel consumer before moving its module** so the suite stays green and the boundary check never spikes. Move logic unchanged; the model's `AgentAction` JSON wire-shape is preserved (R8/R11).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 / US4 (Setup, Foundational, Polish carry no story label)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Package skeleton + the boundary-check ratchet, committed before any extraction.

- [x] T001 [P] Create pack package skeleton: `sr_agent/packs/__init__.py`, `sr_agent/packs/audit/__init__.py`, and empty `sr_agent/packs/audit/{tools,planner,guardrails}/__init__.py`
- [x] T002 [P] Create `tests/architecture/__init__.py` (new test package)
- [x] T003 Implement the boundary check in `tests/architecture/test_kernel_pack_boundary.py` per contracts/boundary-check.md — `ast`-scan every `sr_agent/**/*.py` except `sr_agent/packs/**` and `sr_agent/cli.py`; collect imports; run as a hard `== 0` assertion with a full violation printout (starts green; invert-before-move keeps it 0 at every checkpoint — collapses T027 into this). Verified non-vacuous (catches absolute + relative pack imports).

**Checkpoint**: skeleton present; ratchet reports a baseline (≈0, nothing moved yet); suite green.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The kernel contract types + the dependency inversion that BOTH US1 and US2 require. No user-story work begins until this is done.

**⚠️ CRITICAL**: blocks US1 and US2.

- [ ] T004 [P] Define `CapabilityPack`, `ActionSpec`, `PackContext` frozen dataclasses in `sr_agent/orchestrator/pack.py` (kernel contract types) per data-model.md
- [ ] T005 [P] Define the kernel `Session` `typing.Protocol` (session_id, principal, iterations, token_budget_used) in `sr_agent/models/session.py` per data-model.md (R4)
- [ ] T006 Relocate `Principal` from `sr_agent/models/audit.py` to new kernel module `sr_agent/models/principal.py`; update all importers (`memory/episodic.py`, `io/*`, `models/chat.py`, `cli.py`, `models/audit.py`, …) — this alone removes the memory→audit coupling (R4)
- [ ] T007 Loosen `AgentAction.finding` from `FindingPayload` to `dict | None` in `sr_agent/llm_core/schemas.py` (opaque payload; pack re-validates); keep the JSON wire-shape identical (R8/R11)
- [ ] T008 Invert `validate_action` → `validate_action(action, audit_root, pack)` in `sr_agent/orchestrator/action.py`: consult `pack.actions[type]` for class/reversibility/`validate_params`; **DERIVE the OOB-confirmation requirement from `action_class == write_execute` (kernel rule, R2)**; keep whitelist + path-containment fail-closed even if a pack validator is absent/permissive
- [ ] T009 Assemble an initial `AUDIT_PACK` in `sr_agent/packs/audit/pack.py` that sources the *current* audit definitions (action types, tool entries, dispatch wrapping existing loop logic, domain triggers, prompt) — pack→kernel imports only; lets the system run through the interface before relocation
- [ ] T010 Inject `pack=AUDIT_PACK` at the composition root `sr_agent/cli.py`; thread `pack` into `OrchestratorLoop.__init__` and `ChatReasoningProvider` (both now consume the interface, not audit modules directly)

**Checkpoint**: the audit + chat paths run *through* the `CapabilityPack` interface; full suite green. This is the foundation both stories build on.

---

## Phase 3: User Story 2 - A pack cannot weaken a kernel guarantee (Priority: P1) 🎯 SECURITY MVP

**Goal**: Prove — with tests — that even a hostile pack cannot skip confirmation, forge `human_input`, or opt out of containment/sandbox.

**Independent Test**: `tests/security/test_hostile_pack.py` constructs adversarial `CapabilityPack`s; each forbidden move is rejected/ineffective; the MI harness stays ASR 0.

### Tests for User Story 2 (write first, expect them to hold given T008)

- [ ] T011 [P] [US2] Hostile-pack case **H1** (skip-confirmation on a `write_execute` action, incl. mislabeling it `read_only`) in `tests/security/test_hostile_pack.py` per contracts/hostile-pack.md
- [ ] T012 [P] [US2] Hostile-pack case **H2** (pack `persist_finding`/dispatch tries to write memory at `human_input` tier / fake a status change) in `tests/security/test_hostile_pack.py`
- [ ] T013 [P] [US2] Hostile-pack case **H3** (pack tool with missing/permissive `validate_params`, path escaping `audit_root`, execution outside the sandbox → fail-closed) in `tests/security/test_hostile_pack.py`

### Implementation for User Story 2

- [ ] T014 [US2] Make H1–H3 pass: confirm/repair the kernel enforcement so confirmation is class-derived (`orchestrator/action.py`), the memory source tier is kernel-set for pack writes (`orchestrator/loop.py` + `memory/episodic.py`), and containment/sandbox are unconditional — no `CapabilityPack` field grants a lever (data-model.md "Constraint")

**Checkpoint**: 🔒 the Principle-III security property is proven and green. **Safe stopping point** — if compute runs short, US2 has shipped through the real interface.

---

## Phase 4: User Story 1 - Kernel free of audit-specifics (Priority: P1)

**Goal**: Drive the boundary check to **0** — every audit-specific concept lives under `sr_agent/packs/audit/`, no kernel module imports it.

**Independent Test**: `tests/architecture/test_kernel_pack_boundary.py` reports 0 kernel→pack references; audit code is reachable only via the injected `AUDIT_PACK`.

### Inversions (invert kernel consumers before moving modules — keeps green)

- [ ] T015 [US1] Split `evaluate_triggers` in `sr_agent/guardrails/escalation.py`: keep generic triggers #1/#2/#8; move finding-based #3–#7 to `sr_agent/packs/audit/escalation.py::domain_escalation`; kernel calls generic → then `pack.domain_escalation` (order preserved, R5)
- [ ] T016 [US1] Invert loop execution: move `_dispatch`/`execute_confirmed`/`_persist_finding` bodies to `sr_agent/packs/audit/dispatch.py`; `orchestrator/loop.py` calls `pack.dispatch/execute_confirmed/persist_finding` with a narrow `PackContext`; kernel keeps the control flow + a built-in `read_file`/`search_code` default (R8)
- [ ] T017 [US1] Split `ChatReasoningProvider` in `sr_agent/llm_core/chat_reasoning.py`: drop `models.finding`/`models.audit` imports; consume `pack.reasoning_prompt` + `pack.signal_from`; move the audit prompt + `_finding_from` to `sr_agent/packs/audit/reasoning.py` (R6)
- [ ] T018 [US1] Split the tool registry: keep `ToolDefinition`/`_hash`/`verify_all_hashes`/`ToolTampered` in `sr_agent/tools/registry.py`; move audit tool entries to `sr_agent/packs/audit/registry_entries.py`; verify kernel-builtins ∪ pack tools at loop start (R7)
- [ ] T019 [US1] Extract audit `ActionType` + `ACTION_CLASS_MAP` + `REVERSIBLE` + per-action `validate_params` to `sr_agent/packs/audit/actions.py`; `sr_agent/models/action.py` keeps generic `Action`/`ActionClass`/`ValidationStatus`/`ValidationResult` + the kernel built-in action set (read_file, search_code, write_memory, request_human_confirmation, escalate)

### Relocations (move modules under packs/; update importers)

- [ ] T020 [US1] Relocate `sr_agent/models/finding.py` → `sr_agent/packs/audit/finding.py` (Finding, Severity, BastetTag, SIG, FindingStatus, PoCStatus) + move `FindingPayload` out of `llm_core/schemas.py` into the pack; update pack-side importers
- [ ] T021 [US1] Relocate `AuditSession`/`AuditInput`/`Stage1Report`/`Checkpoint` from `sr_agent/models/audit.py` → `sr_agent/packs/audit/session.py`; retype kernel call sites (`checkpoint.py`, `chat_session.py`, `context.py` drop the dead hint) to the `Session` protocol
- [ ] T022 [P] [US1] Relocate `sr_agent/planner/` → `sr_agent/packs/audit/planner/` and `sr_agent/orchestrator/pipeline.py` → `sr_agent/packs/audit/pipeline.py`; update importers
- [ ] T023 [P] [US1] Relocate audit tools (`static_analysis.py`, `smartgraphical.py`, `onchain.py`, `write_execute.py`) → `sr_agent/packs/audit/tools/`; update importers (they run inside the kernel `DockerSandbox`, unchanged)
- [ ] T024 [P] [US1] Relocate audit guardrails (`mock_detect.py`, `severity.py`) → `sr_agent/packs/audit/guardrails/` and `io/report.py`, `io/input_val.py` → `sr_agent/packs/audit/`; update importers
- [ ] T025 [US1] Move `local_client.py`'s audit `_PROMPT`/`build_analysis_prompt`/`analyze_target` to `sr_agent/packs/audit/reasoning.py`; keep `LocalClient` (generate/ready/warm/available) generic in the kernel

### Close the boundary

- [ ] T026 [US1] Finalize `sr_agent/packs/audit/pack.py::AUDIT_PACK` to source everything from the relocated pack modules; update `sr_agent/cli.py` imports to the new paths (composition root only)
- [ ] T027 [US1] Flip `tests/architecture/test_kernel_pack_boundary.py` to a **hard assertion == 0**; resolve any residual kernel→`sr_agent.packs` import until it passes

**Checkpoint**: ✅ boundary check = 0; audit code lives only under `packs/audit/`; full suite green.

---

## Phase 5: User Story 3 - No behavior change (Priority: P2)

**Goal**: Prove the re-layering changed nothing observable.

**Independent Test**: full suite green (no net loss); a representative audit run + chat turn behave identically; MI harness ASR 0.

- [ ] T028 [US3] Run the full suite (`PYTHONPATH=. .venv/bin/python -m pytest -q`); fix any relocation fallout (imports, serialized class paths, `models/audit.py` removal) until green with no net loss vs. the pre-refactor baseline
- [ ] T029 [US3] Behavioral equivalence spot-check (SC-004): run a fixed audit target and a fixed chat question before/after; confirm same findings/status decisions and same routing/gating/answer
- [ ] T030 [US3] Case **H4**: run the MI harness (`tests/security/`) with the real `AUDIT_PACK` wired; confirm Attack Success Rate = 0 (FR-011)

**Checkpoint**: no regression; the system is safe and identical in behavior.

---

## Phase 6: User Story 4 - Pack contract documented (Priority: P3)

**Goal**: A single doc a future pack author can read; records the no-registry decision.

**Independent Test**: a reviewer checklist confirms the doc enumerates every provided element + every kernel guarantee.

- [ ] T031 [P] [US4] Promote `specs/004-kernel-pack-boundary/contracts/pack-interface.md` into repo docs at `docs/architecture/capability-pack.md`, add the reviewer checklist (provided elements + non-overridable kernel guarantees), and state the no-plugin-registry decision (SC-005/FR-013)
- [ ] T032 [P] [US4] Update `docs/roadmap.md` (Phase 4 status → done) and the architecture diagram under `docs/diagrams/` to show the kernel vs. `sr_agent/packs/audit/` split + the single `cli.py` wiring point

**Checkpoint**: the seam is legible from documentation alone.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T033 [P] Remove transitional shims / temporary re-exports left during relocation; delete dead code (e.g. emptied `models/audit.py`, `io/` if fully moved)
- [ ] T034 Run `specs/004-kernel-pack-boundary/quickstart.md` end-to-end: boundary check, hostile-pack suite, full suite, chat smoke on a real target
- [ ] T035 [P] Final constitution pass: confirm no paid-API dependency entered the core path (Constitution V), `claude_client.py` remains an optional injected transport; capture any gotchas for the Phase-5 lessons queue

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: after Setup — **blocks US1 and US2**.
- **US2 (Phase 3)**: after Foundational. Front-loaded (co-P1) — the security MVP.
- **US1 (Phase 4)**: after Foundational. Ordered after US2 by agreement; T020–T025 relocations depend on their matching inversion (T015–T019) landing first.
- **US3 (Phase 5)**: after US1 (needs boundary 0 + all modules moved). H4 needs the real `AUDIT_PACK`.
- **US4 (Phase 6)**: after US1 (doc reflects final layout); may overlap US3.
- **Polish (Phase 7)**: last.

### Within US1 (critical ordering)

Invert-before-move per module to stay green: T015→(pack escalation), T016→(pack dispatch), T017→(pack reasoning), T018→(pack registry), T019→(pack actions) precede the relocations T020–T025; T026 (final assembly) and T027 (hard boundary assert) close the story.

### Parallel opportunities

- Setup: T001, T002 in parallel.
- Foundational: T004, T005 in parallel (different new files); T006–T010 are sequential (shared files / dependency on the contract types).
- US2 tests: T011, T012, T013 in parallel (same file, distinct cases — coordinate or split into H1/H2/H3 sub-files).
- US1 relocations: T022, T023, T024 in parallel (disjoint module groups) once their inversions land.
- US4: T031, T032 in parallel.

---

## Implementation Strategy

### Security MVP first (Setup + Foundational + US2)

1. Phase 1 Setup → 2. Phase 2 Foundational (system runs through the interface) → 3. Phase 3 US2 (hostile-pack property green). **STOP and VALIDATE**: the Principle-III guarantee is proven through the real interface. This is the safe checkpoint agreed for the compute-limited case.

### Then the full seam (US1 → US3 → US4)

4. Phase 4 US1 relocations, boundary check N→0, green at every module move. 5. Phase 5 US3 no-regression + MI ASR 0. 6. Phase 6 US4 doc. 7. Phase 7 polish.

### Notes

- [P] = different files, no incomplete dependency.
- Commit after each task or logical group (on explicit request per project convention).
- Every relocation is behavior-preserving; if a move changes behavior, split the risk (move first, improve later separately).
- Stop at any checkpoint (end of US2, or after any US1 module move) with a green suite.
