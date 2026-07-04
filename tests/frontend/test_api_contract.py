"""US1 turn contract: start → message → live trace (feature 005, T014).

Drives a REAL turn through the backend with a fake reasoning provider (the
`sessions.provider_factory` seam), so no Ollama is needed. Proves:
  - POST /api/session then /message returns the documented TurnResult shape;
  - the WebSocket streams the ReAct step events for that turn.
The backend is the same loop/pack wiring as cli.py — this checks the surface,
not the kernel (kernel behavior is covered by the unit/security suites).
"""
from __future__ import annotations

import os

os.environ.setdefault("SR_SECRET_KEY", "00" * 32)

import pytest
from fastapi.testclient import TestClient

from sr_agent.llm_core.chat_reasoning import ReasoningOutcome
from sr_agent.llm_core.schemas import AgentAction
from sr_agent.memory.episodic import EpisodicMemory

import frontend.backend.app as appmod
from frontend.backend import sessions
from frontend.backend.app import app
from frontend.backend.sessions import SessionManager

_KEY = bytes(range(32))


class FakeProvider:
    """Answers every turn with a direct 'complete' — no tool, no escalation."""

    def complete(self, messages):
        return ReasoningOutcome(
            kind="action",
            agent_action=AgentAction(next_action="complete", reasoning_summary="hi from the agent"),
            tier="local",
        )


@pytest.fixture
def client(tmp_path):
    # Keep the test off the real ./memory: swap in a tmp-backed manager, and
    # inject the fake provider so a turn runs without a model.
    appmod._manager = SessionManager(EpisodicMemory(memory_root=tmp_path / "mem", secret_key=_KEY))
    sessions.provider_factory = FakeProvider
    with TestClient(app) as c:  # `with` runs lifespan → events.bind_loop
        yield c
    sessions.provider_factory = None


def _start(client) -> str:
    r = client.post("/api/session", json={"project_or_path": ".", "project_id": "testproj"})
    assert r.status_code == 200
    return r.json()["session_id"]


def test_message_returns_turnresult_shape(client):
    sid = _start(client)
    r = client.post(f"/api/session/{sid}/message", json={"text": "hello agent"})
    assert r.status_code == 200
    body = r.json()
    # The documented TurnResult projection (contracts/http-api.md).
    assert body["status"] == "completed"
    assert body["answer"] == "hi from the agent"
    assert body["tier"] == "local"
    assert body["tool_summaries"] == []
    assert body["pending_confirmation_id"] is None
    for key in ("status", "answer", "tier", "pending_action_type", "tool_summaries"):
        assert key in body


def test_session_view_shape(client):
    sid = _start(client)
    r = client.get(f"/api/session/{sid}")
    assert r.status_code == 200
    view = r.json()
    assert view["session_id"] == sid
    assert view["project_id"] == "testproj"
    assert "scope_root" in view and "status" in view


def test_unknown_session_404(client):
    assert client.get("/api/session/does-not-exist").status_code == 404
    assert client.post("/api/session/nope/message", json={"text": "x"}).status_code == 404


def test_ws_streams_trace_for_a_turn(client):
    sid = _start(client)
    with client.websocket_connect(f"/ws/session/{sid}") as ws:
        r = client.post(f"/api/session/{sid}/message", json={"text": "hello"})
        assert r.status_code == 200
        seen = []
        # 'outcome' is always emitted last by the backend → read until it.
        for _ in range(20):
            e = ws.receive_json()
            seen.append(e["type"])
            if e["type"] == "outcome":
                break
    assert seen[0] == "turn_start"          # published before the turn runs
    assert "outcome" in seen                # terminal step streamed
    assert seen[-1] == "outcome"            # ordering preserved (FIFO fan-out)
