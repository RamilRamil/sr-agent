"""Runtime reasoning-backend config + warm (feature 005, US6/R8).

Per-process config the operator sets from the UI: the local-model endpoint
(localhost or a cloud-GPU tunnel), the model name, and an OPTIONAL paid key.
The paid backend is an EXPLICIT selection, never a silent fallback (FR-021). The
key is held only here (in memory), never returned by the API, never persisted,
never logged (Constitution V).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from sr_agent.config import config
from sr_agent.llm_core.gemini_client import SIMPLE_MODELS, GeminiClient
from sr_agent.llm_core.local_client import DEFAULT_HOST, LocalClient


@dataclass
class ModelConfig:
    endpoint: str = DEFAULT_HOST          # LocalClient(host=…) — localhost or a tunnel
    model: str | None = None              # None → for_stage2() (local) / SIMPLE_MODELS[0] (gemini)
    backend: str = "local"                # "local" | "paid" — EXPLICIT operator choice.
    # "paid" builds a GeminiClient — the only paid provider today (spec 018); the
    # UI labels it "Gemini". Kept as "paid" so the generic explicit-paid-selection
    # invariant (and its tests) stay intact.
    _paid_key: str | None = None          # UI Gemini key; overrides env; never returned/logged

    def public(self) -> dict:
        """Serializable view — the secret is write-only (only `has_paid_key`)."""
        return {
            "endpoint": self.endpoint,
            "model": self.model,
            "backend": self.backend,
            "has_paid_key": self._paid_key is not None,
        }

    def local_client(self) -> LocalClient:
        """Build a LocalClient from the current config (used to (re)build a
        session's provider so a config change takes effect next turn — FR-019)."""
        if self.model:
            return LocalClient(model=self.model, host=self.endpoint)
        return LocalClient.for_stage2(host=self.endpoint)

    def effective_gemini_key(self) -> str:
        """The key to use: the UI-provided one wins over the env key (spec 018)."""
        return self._paid_key or config.gemini_api_key

    def reasoning_client(self) -> LocalClient | GeminiClient:
        """The client the session's reasoning provider runs on. Branches on the
        EXPLICIT backend — "paid" builds a GeminiClient, never a silent fallback."""
        if self.backend == "paid":
            return GeminiClient(
                api_key=self.effective_gemini_key(),
                model=self.model or SIMPLE_MODELS[0],
            )
        return self.local_client()


# One process-wide config for this single-operator surface.
CONFIG = ModelConfig()


def set_config(endpoint: str | None = None, model: str | None = None,
               backend: str | None = None, paid_key: str | None = None) -> dict:
    if endpoint is not None:
        CONFIG.endpoint = endpoint
    if model is not None:
        CONFIG.model = model or None
    if backend is not None:
        if backend not in ("local", "paid"):
            raise ValueError("backend must be 'local' or 'paid'")
        CONFIG.backend = backend
    if paid_key is not None:
        CONFIG._paid_key = paid_key or None
    return CONFIG.public()


# ── Tunnel keep-alive + liveness indicator (US6) ─────────────────────────────
# A light periodic ping keeps a cloudflared quick tunnel's connection from idling
# out (~60-100s idle timeout — roadmap gotcha #11) and feeds the live UI dot.
_HEARTBEAT: dict = {"state": "unknown", "endpoint": None, "model": None, "checked_at": None, "fails": 0}


def heartbeat_once() -> dict:
    """One light liveness ping (GET /api/tags) against the current endpoint. Keeps
    the tunnel connection warm and refreshes the indicator state. Never raises."""
    client = CONFIG.local_client()
    try:
        ok = client.available()
    except Exception:
        ok = False
    _HEARTBEAT["endpoint"] = CONFIG.endpoint
    _HEARTBEAT["model"] = client.model
    _HEARTBEAT["checked_at"] = time.time()
    if ok:
        _HEARTBEAT.update(state="up", fails=0)
    else:
        _HEARTBEAT["fails"] = _HEARTBEAT.get("fails", 0) + 1
        _HEARTBEAT["state"] = "down"
    return dict(_HEARTBEAT)


def heartbeat_state() -> dict:
    """The last observed liveness (cheap read — no tunnel traffic)."""
    s = dict(_HEARTBEAT)
    if s.get("checked_at") is not None:
        s["age_s"] = round(time.time() - s["checked_at"], 1)
    return s


def warm() -> dict:
    """Load the model and report state — distinguishes ready from reachable (FR-020).

    Reads the SAME readiness the health projection uses (single source, A2).
    """
    client = CONFIG.local_client()
    start = time.monotonic()
    loaded = client.warm()
    ready = client.ready() if loaded else False
    elapsed = round(time.monotonic() - start, 1)
    if ready:
        state, reason = "ready", None
    elif loaded:
        state, reason = "warming", "loaded but not ready yet"
    else:
        state, reason = "failed", "could not reach/load the model (is Ollama up at the endpoint?)"
    return {"state": state, "reason": reason, "model": client.model, "elapsed_s": elapsed}
