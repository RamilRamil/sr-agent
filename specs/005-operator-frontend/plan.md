# Implementation Plan: Operator Frontend

**Branch**: `005-operator-frontend` | **Date**: 2026-07-04 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-operator-frontend/spec.md`

## Summary

A single-operator web UI to run/observe/control sr-agent solo, built as a **second operator surface** (like `cli.py`) — not a new decision path. A **FastAPI backend imports `sr_agent` + `AUDIT_PACK` directly** and exposes a small read API + a WebSocket live-trace stream + a *deliberately-gated* confirmation surface; a **small Svelte SPA** (Vite build) renders the panels. The distinctive value is the security surface (trust tiers, DATA-wrapping, the OOB confirmation queue, HMAC memory browser, escalation) — no generic chat framework provides that, so those panels are ours; the SPA is the shell.

The one kernel touch is a thin, optional **observability hook**: `OrchestratorLoop` gains an `event_sink` callback it invokes at each step (turn start, intended action + tier + budget, tool dispatched, escalation) and an optional token callback (the local client already streams NDJSON internally, so per-token is cheap). The backend passes a sink that fans events out to the WS. This adds visibility, never authority — it cannot change control flow or weaken an invariant.

The hard constraint (Constitution II, FR-009): **approval is never a reflexive click.** The UI shows the pending-confirmation queue with its `ConsequentialActionNotice`, but approving requires a deliberate review-and-confirm step that writes the *same* out-of-band confirmation record the CLI uses (`request_confirmation`/`check_confirmation`) — the gate is not bypassed, just surfaced.

## Technical Context

**Language/Version**: Python 3.14 (backend, reuses `sr_agent`) + TypeScript/Svelte (SPA). No change to the kernel runtime.

**Primary Dependencies**: `fastapi` + `uvicorn` (backend API + WS), `svelte` + `vite` (SPA, dev/build only). The backend imports `sr_agent` and `sr_agent.packs.audit.pack.AUDIT_PACK` directly. No paid API (Constitution V) — the UI drives the same local-model/relay loop.

**Storage**: None new. The UI reads existing `EpisodicMemory` (HMAC) via the kernel and renders it; it never writes memory itself (writes go through the kernel's gated paths).

**Testing**: `pytest` for the backend (API contract + the no-shortcut gate property); Svelte component tests are optional/light. A backend test asserts FR-009 structurally (no endpoint approves without the deliberate two-step) and FR-016 (no paid-API path).

**Target Platform**: Local, single operator, in a container accessed via `localhost` in a browser (Constitution V / spec Out-of-Scope: no auth, no multi-user, no remote).

**Project Type**: Adds a `frontend/` (backend API + Svelte SPA) alongside the existing `sr_agent/` package — a new operator surface, not a new project.

**Performance Goals**: None hard. "Near-real-time" (SC-002) = events reach the browser within a couple of seconds of happening; on a slow local turn the UI stays visibly alive (liveness ping / token stream).

**Constraints**: Thin view over kernel state + a gated action surface (FR-015); generic panels kernel-level, domain panels pack-contributed (FR-017); the OOB gate is not shortcut (FR-009); no paid API (FR-016); the backend container needs the Docker socket to run the kernel's sandbox (see research R6).

**Scale/Scope**: One operator, one machine. Panels: chat/session, live trace, provenance/trust, confirmation queue, memory browser, escalation, health, modules, audit trail, architecture/help.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Checked against constitution v1.0.0. The UI is another operator surface subject to the same guarantees:

- **I. Secure-Kernel Trust Invariants** — the UI only *renders* kernel state and *streams* observability events; it introduces no new control flow. DATA-wrapping, trust tiers, HMAC memory are surfaced, never altered. The `event_sink` hook is read-only observability. PASS.
- **II. Human Authority** — FR-009 is the crux: approval stays a deliberate act writing the existing OOB confirmation record; no auto-approve, no reflexive one-click. A dedicated backend test enforces "no endpoint approves without the two-step." PASS (by explicit design + test).
- **III. Kernel/Pack Separation** — generic panels read kernel state; domain panels (findings roadmap, PoC status) render pack-produced data; the backend imports the pack only at its composition root (mirrors `cli.py`). The UI does not hardcode audit specifics. PASS.
- **IV. Human-Gated Knowledge** — unaffected; the UI surfaces memory read-only and never promotes anything. PASS.
- **V. No Paid-API Dependency** — the UI drives the same local-first loop; `claude_client` is not required. A test asserts no UI surface needs a paid key. PASS.

**Security Requirements** — the MI harness is unaffected (the UI adds no new untrusted-data path into the loop beyond the user's own message, which is already DATA-wrapped). The one new attack surface — untrusted content rendered in the browser — is handled by the provenance layer rendering DATA as inert, never as controls (FR-007 edge case), and standard output-escaping in the SPA.

No violations to justify; Complexity Tracking omitted.

## Project Structure

### Documentation (this feature)

```text
specs/005-operator-frontend/
├── plan.md              # This file
├── research.md          # Phase 0 — stack + live-trace + gate + container decisions (R1–R7)
├── data-model.md        # Phase 1 — the view/DTO shapes the API exposes
├── quickstart.md        # Phase 1 — build + run the container, open the UI
├── contracts/
│   ├── http-api.md          # REST read endpoints + the gated confirm endpoint
│   ├── live-trace-ws.md     # the WebSocket event stream schema
│   └── approval-gate.md     # the FR-009 "no reflexive click" contract (the security heart)
└── tasks.md             # Phase 2 (/speckit-tasks — not this command)
```

### Source Code (repository root)

```text
frontend/
├── backend/
│   ├── app.py                 # FastAPI app — composition root; imports sr_agent + AUDIT_PACK
│   ├── sessions.py            # drive/observe a chat session over the loop (event_sink → WS)
│   ├── state.py               # read-only projections: health, modules, memory, audit trail, provenance
│   ├── confirm.py             # the deliberate two-step OOB approval (writes the same confirmation record)
│   ├── model_config.py        # runtime reasoning-backend config + warm (US6): endpoint/model/optional key
│   └── events.py              # in-process event bus fanning loop events to WS clients
├── ui/                        # Svelte + Vite SPA
│   ├── src/
│   │   ├── App.svelte
│   │   ├── panels/            # ChatSession, LiveTrace, Provenance, ConfirmQueue, Memory, Escalation, Health, Modules, Settings, AuditTrail, Help
│   │   └── lib/ (api client, ws client, trust-tier styling)
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── Dockerfile                 # multi-stage: node build ui/ → python serves API + static; mounts docker.sock
└── docker-compose.yml         # the frontend service alongside ollama (+ the sandbox via the host socket)

sr_agent/
└── orchestrator/loop.py       # MODIFY (thin): optional `event_sink` + token callback — observability only

tests/
└── frontend/
    ├── test_api_contract.py       # read endpoints return the documented shapes
    ├── test_approval_gate.py      # FR-009: no endpoint approves without the deliberate two-step (security)
    └── test_no_paid_api.py        # FR-016: every surface works local-only
```

**Structure Decision**: A new top-level `frontend/` (Python API + Svelte SPA) next to `sr_agent/`. The backend is a thin composition root that imports the kernel and the pack exactly as `cli.py` does — it is a *surface*, not a fork of the loop. The only kernel edit is an additive, optional observability hook on `OrchestratorLoop`; everything else lives under `frontend/`.

## Complexity Tracking

*No constitution violations to justify — table omitted. The two judgment calls (a SPA + Node build step rather than server-rendered HTMX; mounting the Docker socket into the backend container) are recorded in research R1/R6 with their trade-offs; both are bounded to this local single-operator surface and touch no kernel invariant.*
