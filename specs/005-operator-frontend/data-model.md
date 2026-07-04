# Data Model: Operator Frontend

The frontend adds **no domain data** — it defines **view projections (DTOs)** the API serializes from existing kernel/pack state, plus the live-event shape. Nothing here is persisted by the frontend; all writes go through the kernel's gated paths.

## Read projections (API response shapes)

### `SessionView`
| Field | Source |
|---|---|
| `session_id`, `project_id` | ChatSession / Principal |
| `scope_root` | the loop's `audit_root` |
| `files_read` | tool summaries this session (read_file/search_code targets) |
| `status` | ChatSession.status (active / paused_confirmation / paused_relay / blocked_local_unavailable) |
| `pending_confirmation_id`, `pending_relay_request_id` | ChatSession |

### `ProvenanceBlock`
Every context block, with the trust boundary made legible (FR-007/SC-004).
| Field | Meaning |
|---|---|
| `content` | the text (rendered inert/escaped — never HTML for untrusted tiers) |
| `source_type` | `human_input` \| `tool_output` \| `external_llm_output` \| `llm_inference` |
| `data_wrapped` | bool — was it inside `[DATA START..DATA END]` |
| `tool`, `path`, `flags` | from the DATA-wrap header (sanitize flags) |

### `ConfirmationItem`
| Field | Meaning |
|---|---|
| `id` | confirmation id |
| `action_type`, `params` | the **ConsequentialActionNotice** — exactly what would run |
| `state` | pending / approved / rejected / timed_out |
| `created_at` | timestamp |

### `MemoryRecordView` (read-only)
| Field | Meaning |
|---|---|
| `kind` | finding / checkpoint / status_change / payload(`payload_kind`) |
| `source_type` | trust tier the kernel set |
| `body` | rendered record content (finding fields, checkpoint, status event) |
| `timestamp`, `session_id`, `target` | record metadata |

### `HealthStatus`
`model_ready` (deep probe) vs `model_available` (liveness), `model_name`, `sandbox_up`, `ollama_reachable`. Distinguishes ready≠reachable (SC-006, kernel `LocalClient.ready()` vs `available()`).

### `ModuleDescriptor`
`active_pack` (name), `pack_tools` (name + description + action_class from the pack's registry entries), `kernel_invariants` (static list for the architecture/help view).

### `ModelConfig` (US6 — read/write, per-process)
| Field | Meaning |
|---|---|
| `endpoint` | local-model host/URL (`http://localhost:11434` or a tunnel) → `LocalClient(host=…)` |
| `model` | model name/tag (else `for_stage2()` picks) |
| `has_paid_key` | bool — is an optional paid backend configured (the key value is NEVER returned) |
On read, the key is write-only: the API returns `has_paid_key` but never the secret (FR-021).

### `WarmResult` (US6)
`state` (warming / ready / failed), `reason` (on failure), `model`, `elapsed_s`. Backed by `LocalClient.warm()` then `ready()` — distinguishes ready from merely reachable (FR-020).

### `AuditTrailEntry` (append-only, reconstructed)
`kind` (action_taken / confirmation_decided / tool_run), `detail`, `timestamp`, `session_id` — derived from the memory/confirmation/turn records so a returning operator can reconstruct what happened (US3/SC-005).

## Live event (WebSocket) — `TraceEvent`

Emitted by the loop's `event_sink` (research R3), fanned to WS clients. One JSON object per event:

| `type` | Payload |
|---|---|
| `turn_start` | user_message (as DATA), budget_limit |
| `reasoning` | intended `next_action`, `tool_params`, `reasoning_summary` |
| `routing` | `tier` (local/relay), `escalation_trigger`, `escalation_source` |
| `budget` | `tool_calls_used` / `limit` |
| `tool` | tool name + target (DATA-wrapped result summary) |
| `token` | a generated token (optional; for the "visibly alive" stream, FR-006) |
| `escalation` | which deterministic trigger fired + why |
| `outcome` | completed / paused_confirmation / paused_relay / blocked_local_unavailable / budget_exhausted |

Every event carries a `source_type`/provenance tag so the UI renders tiers correctly; a `token`/`tool` payload from the model is `external_llm_output`, never promotable.

## Pack-contributed (domain) view

`DomainPanel` data is not a new kernel type — the frontend renders **pack-produced records** already in memory (findings roadmap, PoC status via `payload_kind`), tagged by the active pack. A declarative `CapabilityPack.panels` descriptor is the future extension (deferred; no second pack yet — FR-017 / research R5).

## Kernel touch (the only one)

`OrchestratorLoop.__init__` gains `event_sink: Callable[[dict], None] | None = None` (and optionally `token_sink`). Additive, default `None`, observability-only — it cannot alter control flow or any invariant. Everything else is under `frontend/`.
