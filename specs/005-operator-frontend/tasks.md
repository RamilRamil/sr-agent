# Tasks: Operator Frontend

**Input**: Design documents from `/specs/005-operator-frontend/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R8), data-model.md, contracts/{http-api,live-trace-ws,approval-gate}.md

**Tests**: INCLUDED for the security-critical + constitution properties — the approval gate (FR-009, US2) and no-paid-API (FR-016/021) are the ones that MUST be proven; plus a light API-contract test. UI component tests are optional/omitted.

**Organization**: By user story, in priority order — US1 (P1, MVP) → US2 (P1, security) → US6 (P2, practical: point at a model) → US3/US4 (P2) → US5 (P3). The backend is a composition root that imports `sr_agent` + `AUDIT_PACK` exactly like `cli.py`; the only kernel edit is an additive, optional observability hook.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files, no dependency on an incomplete task
- **[Story]**: US1…US6 (Setup/Foundational/Polish carry no story label)

---

## Phase 1: Setup

- [X] T001 [P] Scaffold `frontend/backend/` — FastAPI app skeleton + deps (`fastapi`, `uvicorn[standard]`) in `frontend/backend/requirements.txt`
- [ ] T002 [P] Scaffold `frontend/ui/` — Svelte + Vite project (`package.json`, `vite.config.ts` proxying `/api`+`/ws` to the backend, `index.html`, `src/App.svelte`)
- [ ] T003 [P] Add `frontend/Dockerfile` (multi-stage: node builds `ui/` → python serves API + static) and `frontend/docker-compose.yml` (mounts `/var/run/docker.sock`, joins the `ollama` network — research R6)

**Checkpoint**: backend serves a hello route; SPA dev server loads; container builds.

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: blocks all user stories.

- [X] T004 Add the kernel observability hook in `sr_agent/orchestrator/loop.py`: optional `event_sink: Callable[[dict], None] | None = None` (and `token_sink`) on `__init__`, emitted at each step of `run_turn` (turn_start, reasoning, routing, budget, tool, escalation, outcome). Additive, `None`-safe — existing suite MUST stay green (observability only, no control-flow change; research R3)
- [X] T005 [P] `frontend/backend/app.py` — FastAPI composition root: import `sr_agent` + `AUDIT_PACK`, build `EpisodicMemory`/`ChatReasoningProvider`/`OrchestratorLoop(pack=AUDIT_PACK, event_sink=…)` like `cli.py`; mount routes + static SPA
- [X] T006 [P] `frontend/backend/events.py` — in-process event bus: per-session async queues; the loop's `event_sink` publishes, WS clients subscribe
- [X] T007 [P] `frontend/backend/state.py` — read-only projections per data-model.md (`SessionView`, `ProvenanceBlock`, `MemoryRecordView`, `HealthStatus`, `ModuleDescriptor`, `AuditTrailEntry`); NEVER calls `memory.write`
- [ ] T008 [P] SPA shared lib in `frontend/ui/src/lib/`: `api.ts` (REST), `ws.ts` (WebSocket), `trust.ts` (SourceType→style + inert-render helpers; no `{@html}` on untrusted — research R7)

**Checkpoint**: backend runs through the kernel via the pack; event bus streams a stub event; SPA can call a read endpoint.

---

## Phase 3: User Story 1 — Run & observe a session (Priority: P1) 🎯 MVP

**Goal**: Start/resume a session bound to a folder, send messages, watch the live trace.

**Independent Test**: Point at a folder, send a question, see the reply + a live step-by-step trace; reload and resume.

- [X] T009 [US1] `frontend/backend/sessions.py` — `POST /api/session` (start bound session) + `POST /api/session/{id}/message` (`loop.run_turn` with the `event_sink`→bus); returns the `TurnResult` projection
- [X] T010 [US1] `WS /ws/session/{id}` in `frontend/backend/app.py` — stream `TraceEvent`s per contracts/live-trace-ws.md
- [X] T011 [P] [US1] `GET /api/session/{id}` → `SessionView` (scope root, files read, status) in `frontend/backend/app.py`
- [ ] T012 [P] [US1] `frontend/ui/src/panels/ChatSession.svelte` — start/send/reply, bound project + working scope
- [ ] T013 [P] [US1] `frontend/ui/src/panels/LiveTrace.svelte` — subscribe WS, render step events + tier/budget + token liveness (FR-004–006)
- [ ] T014 [US1] `tests/frontend/test_api_contract.py` — session start/message and the WS emit the documented shapes

**Checkpoint**: an operator drives a full turn from the browser and watches it live. **MVP.**

---

## Phase 4: User Story 2 — Approve/reject safely (Priority: P1) 🔒 SECURITY

**Goal**: The confirmation queue + the deliberate two-step approval that never shortcuts the gate.

**Independent Test**: Drive a write/PoC action → it pauses in the queue → approval requires a deliberate act → executes only then.

- [X] T015 [US2] `GET /api/confirmations?session={id}` → `ConfirmationItem[]` with the `ConsequentialActionNotice` (what would run). Fetching an item's notice ISSUES the short-lived `confirm_token` bound to that id (the deliberate-act prerequisite for T016, C3)
- [X] T016 [US2] `frontend/backend/confirm.py` — the deliberate two-step: a `confirm_token` issued only on fetching an item's notice; `POST /api/confirm/{id}` (with token + decision) writes the SAME OOB confirmation record as `sr-agent confirm` (reuses `confirmation.py`); NO auto-approve, NO reflexive one-click (contracts/approval-gate.md)
- [ ] T017 [P] [US2] `frontend/ui/src/panels/ConfirmQueue.svelte` — review-notice → deliberate confirm (distinct from browsing); also displays the `sr-agent confirm <id> --approve` fallback command
- [X] T018 [US2] `tests/frontend/test_approval_gate.py` (SECURITY) — G1: write_execute pauses & doesn't execute; G2: no/invalid token → no approval; G3: only a post-notice token approves, via the kernel's `execute_confirmed`; G4: no code path auto-approves

**Checkpoint**: 🔒 approval is hosted in the UI without weakening the gate — proven by test.

---

## Phase 5: User Story 6 — Model backend config + warm (Priority: P2)

**Goal**: Set the local-model endpoint (localhost / tunnel) + optional paid key, and a warm button with model state.

**Independent Test**: Set the endpoint, press warm, see ready; no paid key needed for anything.

- [X] T019 [US6] `frontend/backend/model_config.py` — per-process `ModelConfig` (endpoint/model/optional key) + `GET`/`POST /api/model/config` (key write-only: never returned/persisted/logged) + `POST /api/model/warm` → `WarmResult` (`LocalClient.warm()`+`ready()`); the paid backend is an EXPLICIT selection, never a silent fallback (FR-021/R8). A config change **rebuilds the active session's reasoning provider** so its next turn uses the new backend (FR-019, C2). `warm`/readiness reads the **same `HealthStatus` projection** as the health panel (single source — no second impl, A2)
- [ ] T020 [P] [US6] `frontend/ui/src/panels/Settings.svelte` — set local endpoint/model (tunnel-friendly), optional paid key, explicit backend selector, warm button + live state (warming→ready/failed)
- [X] T021 [US6] `tests/frontend/test_no_paid_api.py` — every surface functions with no key (FR-016/021); `GET /api/model/config` never returns the secret

**Checkpoint**: operator points the agent at a tunnel and warms it from the UI, no restart.

---

## Phase 6: User Story 3 — Reconstruct what happened (Priority: P2)

- [ ] T022 [P] [US3] `GET /api/memory?project={id}` (`MemoryRecordView[]`, read-only) + `GET /api/audit?session={id}` (`AuditTrailEntry[]`) in `frontend/backend/app.py`
- [ ] T023 [P] [US3] `frontend/ui/src/panels/Memory.svelte` + `AuditTrail.svelte` — read-only browser + append-only reconstruction (no edit/delete)

**Checkpoint**: a returning operator reconstructs the session from memory + audit trail alone.

---

## Phase 7: User Story 4 — See the trust boundary (Priority: P2)

- [ ] T024 [P] [US4] `GET /api/session/{id}/context` → `ProvenanceBlock[]` (tier-tagged, DATA-wrap flagged); escalation events surfaced in the WS stream
- [ ] T025 [P] [US4] `frontend/ui/src/panels/Provenance.svelte` + `Escalation.svelte` — tier tags + visible `[DATA]` wrappers, untrusted content rendered INERT (escaped, never `{@html}`; research R7), escalation trigger + reason
- [ ] T026 [US4] `tests/frontend/test_provenance.py` — every block carries its tier; untrusted DATA is delivered for inert render (display-layer injection guard)

**Checkpoint**: the trust boundary is legible; injected content cannot masquerade as UI.

---

## Phase 8: User Story 5 — Makeup & health (Priority: P3)

- [ ] T027 [P] [US5] `GET /api/health` (`ready` vs `available`, sandbox, ollama) + `GET /api/modules` (active pack + tools + kernel invariants) + `GET /api/domain/panels?session={id}` (pack-produced domain data, FR-017)
- [ ] T028 [P] [US5] `frontend/ui/src/panels/Health.svelte` + `Modules.svelte` + `Help.svelte` (architecture/kernel-pack + invariants reference)
- [ ] T029 [P] [US5] Render pack-contributed domain panels (findings roadmap / PoC status) from `/api/domain/panels`, tagged by active pack — generic panels unchanged when the pack changes (SC-008)

**Checkpoint**: operator can tell readiness + active modules; domain panels are pack-driven.

---

## Phase 9: Polish & Cross-Cutting

- [ ] T030 [P] Compose `frontend/ui/src/App.svelte` — the panel layout tying all panels together
- [ ] T031 [P] Finalize `frontend/Dockerfile` + `docker-compose.yml`; run `quickstart.md` end-to-end (build, open localhost, drive a turn, warm a model)
- [ ] T032 Constitution pass: no surface requires a paid key (FR-016); `event_sink` is observability-only (existing kernel suite still green); no `{@html}` on untrusted content anywhere; capture any gotchas for the Phase-5 lessons queue

---

## Dependencies & Execution Order

- **Setup (P1)** → **Foundational (P2, blocks all)** → user stories.
- **US1 (P1)** is the MVP and the base every other panel renders beside; do it first.
- **US2 (P1)** depends on US1's session/turn (a write action arises from a turn).
- **US6/US3/US4 (P2)** depend only on Foundational + US1; independent of each other.
- **US5 (P3)** independent; last.
- The kernel hook **T004** is the single shared prerequisite for the live trace (US1) — do it in Foundational.

### Parallel opportunities

- Setup: T001/T002/T003 in parallel.
- Foundational: T005/T006/T007/T008 in parallel after T004.
- Within a story: backend endpoint + its SPA panel are separate files → the `[P]` panel tasks parallel the endpoint tasks.
- The three test tasks (T014/T018/T021/T026) are independent files.

---

## Implementation Strategy

### MVP (Setup + Foundational + US1)
Drive + observe a session from the browser. STOP and validate: a real turn runs and streams live.

### Then security + practical (US2 → US6)
US2 makes approval safe (the security property, tested); US6 makes it usable against a tunnel/model. These two make it a real operator tool.

### Then the rest (US3 → US4 → US5 → Polish)
Observability-after-the-fact, trust legibility, introspection, then container/docs finalize.

### Notes
- The backend is a surface, not a fork: it constructs the same loop/pack as `cli.py`.
- The only kernel change is T004 (additive, observability-only) — keep the existing suite green.
- Approval NEVER becomes a reflexive click (T016/T018) — this is the feature's non-negotiable.
- Commit per task or logical group (on explicit request per project convention).
