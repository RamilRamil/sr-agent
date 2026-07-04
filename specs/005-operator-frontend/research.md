# Research: Operator Frontend

Phase 0 decisions. Grounded in the constitution (thin surface, own the control plane, no paid dependency, local single operator) and the existing kernel (a Python package with `cli.py` as the reference operator surface).

## R1 — UI rendering stack

**Decision**: A small **Svelte + Vite SPA** talking to the backend over HTTP + WebSocket. (Operator-selected: FastAPI + small SPA.) Svelte over React for a small app — lighter bundle, less boilerplate, no virtual-DOM ceremony for what is mostly live panels; React is a drop-in alternative if preferred.

**Rationale**: The operator chose a richer SPA over server-rendered HTMX for the live "what the agent is thinking" visualization. Svelte keeps the JS footprint minimal, which respects the "thin" spirit as much as a SPA can. The build step is dev-only; the shipped artifact is static files the backend serves.

**Alternatives considered**: Server-rendered HTMX+SSE (lighter, no Node) — not chosen; the operator wanted a real SPA for the reasoning visualization. React (bigger ecosystem for graph viz) — fine, but heavier than needed for v1. TUI-in-browser (Textual) — rejected; the spec says web UI.

## R2 — Backend

**Decision**: **FastAPI + uvicorn**, a thin app that imports `sr_agent` and `sr_agent.packs.audit.pack.AUDIT_PACK` directly and is a **composition root** (like `cli.py`): it constructs `OrchestratorLoop(..., pack=AUDIT_PACK)`, `EpisodicMemory`, `ChatReasoningProvider`, exactly as the CLI does. REST for reads, WebSocket for the live trace, one gated endpoint for confirmations.

**Rationale**: The kernel is Python; importing it directly is the least-layers, least-drift option (no second serialization of the domain). FastAPI gives typed request/response + first-class WebSocket + auto OpenAPI (useful as the contract). Being a composition root keeps it symmetric with `cli.py` and honours FR-015 (a surface, not a new decision path).

**Alternatives considered**: A separate process the UI shells out to the CLI — rejected; loses live state and re-parses CLI output. Flask/stdlib http.server — workable but no native WS/typed models; FastAPI is the smaller total effort.

## R3 — Live trace ("what the agent is thinking now")

**Decision**: Add a thin, optional **`event_sink: Callable[[dict], None] | None`** to `OrchestratorLoop`. The loop calls it at each meaningful step — turn start; intended `next_action` + params + `reasoning_summary`; routing tier + escalation trigger/source; per-turn tool-call budget used; tool dispatched; terminal/paused outcome. The backend passes a sink that puts events on an in-process bus (`events.py`) fanned out to WS clients. **Token streaming** is available cheaply because `LocalClient.generate()` already streams NDJSON internally — a second optional `token_sink` can forward tokens for the "visibly alive" indicator (FR-006); v1 may ship per-step events + a liveness ping and add per-token later.

**Rationale**: The live view needs step-level events the synchronous `run_turn` return can't provide. An event-sink callback is pure observability — it cannot alter control flow, tool selection, or any invariant (Constitution I), so it is a safe kernel addition. It is `None` by default, so the CLI and tests are unaffected.

**Alternatives considered**: Polling kernel state — too coarse for "current step" and misses the sub-second liveness. Parsing logs — brittle. Rewriting the loop to be async-generator-based — larger change than a callback, and risks the security-critical control flow.

## R4 — The OOB approval gate in a GUI (FR-009 — the security heart)

**Decision**: The UI **shows** the pending-confirmation queue (each item's `ConsequentialActionNotice` — exactly what would run). Approval is a **deliberate two-step**: the operator opens the item, reviews the notice, and performs an explicit confirm action that writes the **same out-of-band confirmation record** the CLI's `sr-agent confirm` writes (via the existing `confirmation.py` primitives). There is **no auto-approve** and **no single navigation-equivalent click** that approves — approving is structurally distinct from browsing. The backend's confirm endpoint requires the item id **and** an explicit confirm token/step tied to having viewed the notice; a plain GET/navigation never approves.

**Rationale**: Constitution II says a convenience surface must not shortcut the human-authority gate. Reusing the file-based confirmation record means the UI approval and the CLI approval are the *same* act through the *same* gate — the GUI is a viewer + a deliberate trigger, not a new authority. A dedicated test asserts the property: no request path approves a pending action without the two-step.

**Alternatives considered**: A one-click "Approve" button next to the queue — rejected; that is exactly the reflexive shortcut FR-009 forbids. Keeping approval CLI-only (UI shows the command to run) — safe, and kept as a fallback, but the operator wanted to act from the UI; the two-step in-UI act preserves the guarantee while staying usable.

## R5 — Kernel/pack panel split (FR-017)

**Decision**: **Generic panels** (chat/session, live trace, provenance/trust, confirmation queue, memory browser, health, modules, audit trail) read only kernel state and work for any pack. **Domain panels** (findings roadmap, PoC status, SIG/graph) render **pack-produced data** the kernel already persists (findings/checkpoints/status events in `EpisodicMemory`, the findings-roadmap view) — the frontend does not hardcode audit specifics; it renders what the active pack has produced. A future `CapabilityPack.panels` descriptor (declarative panel metadata) is the clean extension when a second pack exists — **not built now** (YAGNI, consistent with 004's no-registry stance).

**Rationale**: Keeps the frontend consistent with the 004 seam: generic surface is pack-agnostic; domain content comes from the pack. For v1 the domain data is already in memory (roadmap/findings), so no new pack interface is needed — the panel just renders pack-produced records, tagged by `payload_kind`.

**Alternatives considered**: Hardcode audit panels in the frontend — rejected (breaks FR-017). Add `CapabilityPack.panels` now — deferred (no second pack; YAGNI).

## R6 — Container + the sandbox (Docker socket)

**Decision**: The backend runs in a container (multi-stage Dockerfile: Node builds `ui/`, Python serves the API + static files). Because the kernel's `DockerSandbox` shells out to `docker run` (for PoC/analyzer execution), the backend container **mounts the host Docker socket** (`/var/run/docker.sock`) and has the `docker` CLI. `docker-compose.yml` wires it alongside the existing `ollama` service; the ephemeral sandbox containers are launched on the host via the socket.

**Rationale**: The sandbox is a kernel invariant (network-isolated, ephemeral) that must keep working from the UI-driven path. Mounting the socket is the standard way to let a container orchestrate sibling containers for a **local, single-operator** tool. It is a real privilege (socket ≈ host root), acceptable here because this is a local dev surface with no auth/remote (spec Out-of-Scope) — and it is called out so it is a conscious choice, not a hidden one.

**Alternatives considered**: Docker-in-Docker — heavier, no benefit locally. Run the backend on the host (uncontainerized) — contradicts FR-018 ("in a container"); the socket mount keeps the container requirement while letting the sandbox run.

## R7 — Rendering untrusted content safely (FR-007 edge case)

**Decision**: The provenance layer tags every context block with its `SourceType` and marks DATA-wrapped (external/untrusted) content distinctly. Untrusted content is rendered as **inert text** (escaped, never as HTML/controls) — it can never act as a UI control or be mistaken for trusted chrome. Trusted orchestrator content and untrusted DATA are visually separated (color/border + a tier label), and the `[DATA START..DATA END]` markers are shown, not stripped.

**Rationale**: The whole project resists injection; the browser is a new render target where injected content could try to masquerade as UI. Escaping + explicit tier styling makes the trust boundary legible (SC-004) and closes the display-layer injection vector. Svelte escapes interpolated text by default; the plan forbids `{@html}` on any model/tool-originated content.

**Alternatives considered**: Render markdown/HTML from model output for nicer formatting — rejected for untrusted content (injection risk); if formatting is wanted, it is applied only to trusted orchestrator text, never to DATA blocks.

## R8 — Runtime model-backend config + warm control (US6, FR-019–FR-021)

**Decision**: A **settings panel** + backend `config.py` hold a per-process **reasoning-backend config**: local-model `endpoint` (host/URL — maps to `LocalClient(host=…)`, the same knob used to point at a Colab tunnel), `model` name, and an **optional paid API key**. Turns construct the client from the current config (default `localhost:11434` / `for_stage2()`), so changing it takes effect on the next turn — no restart, no env var (FR-019). A **warm** endpoint calls `LocalClient.warm()` then `ready()` and returns the state (warming → ready / failed + reason), and the health panel shows `ready` vs `available` (FR-020, kernel already distinguishes these). A provided paid key is held only in process/session memory and enables `ClaudeClient` as an optional backend for that operator — the local path always works with no key (FR-021, Constitution V).

**Rationale**: This is exactly the operator's real workflow — a weak local box pointed at a cloud-GPU tunnel — made first-class instead of an env-var dance. `LocalClient` already takes `host`; the streaming `generate()` already survives a tunnel's idle timeout (roadmap gotcha #11). Warm-on-demand + ready≠reachable is the honest signal the operator needs before spending minutes on a slow turn.

**Constitution V nuance**: allowing an optional paid key does NOT make the core depend on it — the default and the always-available path is the local model / relay; the key is per-operator, optional, never persisted (not to memory, not committed). A test asserts every surface works with no key. Entering a secret in a browser form is acceptable because this is a localhost single-operator surface (no auth/remote by design); the key is never logged or written to disk.

**Explicit-selection rule (resolves the FR-011 tension)**: a paid backend is a backend the operator **explicitly picks** in the settings panel — never an automatic fallback. The local-first chat design (feature 003, FR-011) forbids *silently* redirecting an unavailable local model to relay/paid; it does NOT forbid the operator deliberately choosing a different backend. So the settings panel offers an explicit backend selector (local endpoint / paid model), and "local unavailable" still yields refuse-and-wait unless the operator has chosen paid — the two are consistent.

**Alternatives considered**: Config via env vars only (status quo) — rejected; the operator explicitly wants to set the endpoint from the UI. Persisting the config/key to a file — rejected for the key (secret); the non-secret endpoint/model MAY be remembered in a local, gitignored settings file, but the key stays in memory.

