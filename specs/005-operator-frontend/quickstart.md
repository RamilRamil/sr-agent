# Quickstart: Operator Frontend

A local, single-operator web UI over sr-agent. Runs in a container alongside Ollama; open it in a browser on `localhost`.

## Prerequisites

- Docker running (Ollama container + the ephemeral sandbox), a pulled local model (`for_stage2` picks it).
- `SR_SECRET_KEY` set (HMAC memory), same as any sr-agent surface.
- No `ANTHROPIC_API_KEY` needed — the UI drives the local model / relay only (FR-016).

## Build & run (container)

```bash
cd /Users/ramilmustafin/Claude/Projects/SR-agent
# multi-stage: Node builds the Svelte SPA, Python serves API + static
docker compose -f frontend/docker-compose.yml up --build
```

The compose service mounts the host Docker socket (so the kernel's `DockerSandbox` can launch sibling containers — research R6) and joins the network with `ollama`. Then open:

> ⚠️ **Local-only by design.** Mounting `/var/run/docker.sock` gives this container host-root-equivalent access — that's why it stays a **localhost, single-operator** tool with no auth/remote. Do not expose it to a network. (The sandbox itself is still ephemeral + `--network none`; the socket is only how the kernel launches it.)


```
http://localhost:8000
```

## Dev loop (without a full container rebuild)

```bash
# backend (imports sr_agent directly)
SR_SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))") \
  PYTHONPATH=. .venv/bin/uvicorn frontend.backend.app:app --reload

# SPA (Vite dev server, proxies /api + /ws to the backend)
cd frontend/ui && npm install && npm run dev
```

## What you can do

- **Start a session** bound to a target folder, send messages, watch the **live trace** (intended action, tier, budget, tokens) stream in.
- **Approve/reject** a PoC/write action from the **confirmation queue** — a deliberate two-step that writes the same OOB record as `sr-agent confirm` (never a reflexive click; see contracts/approval-gate.md). Or copy the shown `sr-agent confirm <id> --approve` and do it from the terminal.
- **See the trust boundary**: every block tagged by tier, DATA-wrapped content visually distinct and inert.
- **Browse memory** (findings/checkpoints/status, read-only), the **audit trail** of what happened while you were away, **health** (model ready vs available, sandbox up), and **modules** (active pack + its tools + kernel invariants).

## Verifying the security property (the point)

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/frontend/test_approval_gate.py -v
```

Proves FR-009: a `write_execute` turn pauses and never executes without the deliberate two-step; no endpoint auto-approves. Also:

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/frontend/test_no_paid_api.py -v   # FR-016
```

## Where things live

- **Backend (composition root, imports the kernel + AUDIT_PACK)**: `frontend/backend/`
- **SPA**: `frontend/ui/`
- **Only kernel touch**: `sr_agent/orchestrator/loop.py` — an optional `event_sink` (observability, default off).
