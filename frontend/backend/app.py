"""Operator frontend backend — FastAPI composition root (feature 005).

Imports sr_agent + AUDIT_PACK directly (a second operator surface, like cli.py).
REST reads + a WebSocket live trace + a deliberately-gated confirm. No paid API
required for any surface (Constitution V / FR-016).
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from sr_agent.config import config
from sr_agent.memory.episodic import EpisodicMemory

from frontend.backend import confirm, events, model_config, state
from frontend.backend.sessions import SessionManager


@asynccontextmanager
async def _lifespan(app: FastAPI):
    events.bind_loop(asyncio.get_running_loop())  # let the sync event_sink cross into the WS loop
    yield


app = FastAPI(title="SR-agent operator frontend", lifespan=_lifespan)

_memory = EpisodicMemory(config.memory_root, config.secret_key)
_manager = SessionManager(_memory)


# ── System / introspection (US5) ─────────────────────────────────────────────
@app.get("/api/health")
def get_health() -> dict:
    return state.health()


@app.get("/api/modules")
def get_modules() -> dict:
    return state.modules()


# ── Model backend config + warm (US6) ────────────────────────────────────────
@app.get("/api/model/config")
def get_model_config() -> dict:
    return model_config.CONFIG.public()  # never returns the key


@app.post("/api/model/config")
def post_model_config(body: dict) -> dict:
    try:
        return model_config.set_config(
            endpoint=body.get("endpoint"), model=body.get("model"),
            backend=body.get("backend"), paid_key=body.get("paid_key"),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/model/warm")
async def post_warm() -> dict:
    return await run_in_threadpool(model_config.warm)


# ── Session (US1) ─────────────────────────────────────────────────────────────
@app.post("/api/session")
def post_session(body: dict) -> dict:
    try:
        s = _manager.start(body.get("project_path", ""), body.get("project_id"))
    except ValueError as e:
        raise HTTPException(400, str(e))  # explicit external path required
    return {
        "session_id": s.chat.session_id,
        "project_id": s.chat.principal.project_id,
        "scope_root": str(s.loop._audit_root),
    }


@app.get("/api/session/{session_id}")
def get_session(session_id: str) -> dict:
    s = _manager.get(session_id)
    if s is None:
        raise HTTPException(404, "session not found")
    return {
        "session_id": s.chat.session_id,
        "project_id": s.chat.principal.project_id,
        "scope_root": str(s.loop._audit_root),
        "status": s.chat.status,
        "pending_confirmation_id": s.chat.pending_confirmation_id,
    }


@app.post("/api/session/{session_id}/message")
async def post_message(session_id: str, body: dict) -> dict:
    s = _manager.get(session_id)
    if s is None:
        raise HTTPException(404, "session not found")
    text = body["text"]
    events.publish(session_id, {"type": "turn_start", "user_message": text, "source_type": "human_input"})
    result = await run_in_threadpool(s.loop.run_turn, text, "")
    s.chat.status = {"paused_confirmation": "paused_confirmation", "paused_relay": "paused_relay",
                     "blocked_local_unavailable": "blocked_local_unavailable"}.get(result.status, "active")
    s.chat.pending_confirmation_id = result.pending_confirmation_id
    events.publish(session_id, {"type": "outcome", "status": result.status, "source_type": "tool_output"})
    return {
        "status": result.status, "answer": result.answer,
        "tier": result.routing.tier if result.routing else "local",
        "pending_confirmation_id": result.pending_confirmation_id,
        "pending_action_type": result.pending_action_type,
        "pending_action_params": result.pending_action_params,
        "tool_summaries": result.tool_summaries,
    }


@app.get("/api/memory")
def get_memory(project: str) -> list[dict]:
    return state.memory_records(_memory, project)


@app.get("/api/domain/panels")
def get_domain_panels(session: str, project: str) -> dict:
    """Pack-contributed domain panels (SC-008) — generic surface, pack content."""
    return state.domain_panels(_memory, session, project)


# ── Confirmation queue + the deliberate gate (US2 / FR-009) ───────────────────
@app.get("/api/confirmations")
def list_confirmations() -> list[dict]:
    """The pending queue (browsing only — no confirm_token issued here)."""
    return confirm.list_pending(config.confirmations_root)


@app.get("/api/confirmations/{confirmation_id}")
def get_confirmation(confirmation_id: str) -> dict:
    """Fetch the notice — and issue the confirm_token (the deliberate-act prerequisite)."""
    try:
        return confirm.load_notice(confirmation_id, config.confirmations_root)
    except FileNotFoundError:
        raise HTTPException(404, "confirmation not found")


@app.post("/api/confirm/{confirmation_id}")
async def post_confirm(confirmation_id: str, body: dict) -> dict:
    try:
        status = confirm.decide(
            confirmation_id, body.get("confirm_token"), body.get("decision", ""),
            config.confirmations_root,
        )
    except confirm.ApprovalError as e:
        raise HTTPException(403, str(e))
    except FileNotFoundError:
        raise HTTPException(404, "confirmation not found")
    return {"confirmation_id": confirmation_id, "status": status.value}


# ── Live trace (US1) ──────────────────────────────────────────────────────────
@app.websocket("/ws/session/{session_id}")
async def ws_trace(ws: WebSocket, session_id: str) -> None:
    await ws.accept()
    q = events.subscribe(session_id)
    try:
        while True:
            event = await q.get()
            await ws.send_text(json.dumps(event))
    except WebSocketDisconnect:
        pass
    finally:
        events.unsubscribe(session_id, q)


# ── Static SPA (built into frontend/ui/dist) ──────────────────────────────────
_DIST = Path(__file__).resolve().parents[1] / "ui" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="spa")
