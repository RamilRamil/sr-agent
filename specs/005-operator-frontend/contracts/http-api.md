# Contract: HTTP API

The backend's REST surface. All localhost, single operator, no auth (spec Out-of-Scope). Reads are projections of kernel state (data-model.md); the only state-changing calls are starting a session, sending a turn, and the **deliberately-gated** confirm (see approval-gate.md).

## Read endpoints (projections — never mutate kernel state)

| Method · Path | Returns | Serves |
|---|---|---|
| `GET /api/health` | `HealthStatus` | US5 — model ready vs available, sandbox, ollama |
| `GET /api/modules` | `ModuleDescriptor` | US5 — active pack + its tools + kernel invariants |
| `GET /api/session/{id}` | `SessionView` | US1 — bound project, scope, files read, status |
| `GET /api/session/{id}/context` | `ProvenanceBlock[]` | US4 — trust-tagged context (DATA-wrapping visible) |
| `GET /api/memory?project={id}` | `MemoryRecordView[]` | US3 — HMAC memory browser (read-only) |
| `GET /api/audit?session={id}` | `AuditTrailEntry[]` | US3 — append-only reconstruction |
| `GET /api/confirmations?session={id}` | `ConfirmationItem[]` | US2 — pending queue + notices |
| `GET /api/domain/panels?session={id}` | pack-produced panel data | US1 — findings roadmap / PoC status (pack-tagged) |
| `GET /api/model/config` | `ModelConfig` | US6 — current backend (endpoint, model, `has_paid_key`; key never returned) |

## Action endpoints (the surface, gated by the kernel)

| Method · Path | Body | Effect |
|---|---|---|
| `POST /api/session` | `{ project_or_path, project_id? }` | start a session bound to a target (reuses the loop/chat wiring; FR-001) |
| `POST /api/session/{id}/message` | `{ text }` | run one turn (`loop.run_turn`); streams via the WS; returns the `TurnResult` projection. A `write_execute`/privileged turn **pauses** and appears in `/api/confirmations` — it does NOT execute here (FR-005/FR-008) |
| `POST /api/confirm/{confirmation_id}` | `{ confirm_token, decision: approve\|reject }` | the **deliberate two-step** approval — see approval-gate.md. Requires a `confirm_token` issued only after the notice was fetched; a bare/mis-tokened call never approves (FR-009) |
| `POST /api/model/config` | `{ endpoint?, model?, paid_key? }` | set the reasoning backend at runtime (FR-019/FR-021). `paid_key` held in-process only, never returned/persisted/logged; next turn uses the new config |
| `POST /api/model/warm` | `{}` | load the model, return `WarmResult` (warming → ready / failed) — the warm button (FR-020) |

## Invariants the API upholds

- **No memory writes from read endpoints** — reads never call `EpisodicMemory.write`.
- **No paid API** — every endpoint functions with the local model / relay only; none requires `ANTHROPIC_API_KEY` (FR-016; tested).
- **The kernel enforces gating** — `/message` cannot execute a write_execute action; only `/confirm` (post-approval) reaches `execute_confirmed`, exactly as the CLI does.
- **Provenance preserved** — `/context` and WS events carry `source_type`; untrusted content is delivered for inert rendering, never as HTML.
