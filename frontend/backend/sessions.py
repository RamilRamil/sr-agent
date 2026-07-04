"""Session management (feature 005, US1).

Builds an OrchestratorLoop per chat session — the SAME wiring as cli.py's chat
command (pack=AUDIT_PACK, ChatReasoningProvider over a LocalClient) — plus the
event_sink so the live trace streams to the WS. A provider factory can be
overridden (tests inject a fake provider so a turn can be driven without Ollama).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from sr_agent.config import config
from sr_agent.llm_core.chat_reasoning import ChatReasoningProvider
from sr_agent.memory.episodic import EpisodicMemory
from sr_agent.models.chat import ChatSession
from sr_agent.models.principal import Principal
from sr_agent.orchestrator.chat_session import save_session
from sr_agent.orchestrator.loop import OrchestratorLoop
from sr_agent.packs.audit.escalation import domain_escalation
from sr_agent.packs.audit.pack import AUDIT_PACK
from sr_agent.packs.audit.reasoning import AUDIT_CHAT_SYSTEM, signal_from
from sr_agent.packs.audit.session import AuditInput, AuditSession

from frontend.backend import events
from frontend.backend.model_config import CONFIG

# Test seam: override to inject a fake reasoning provider (drive a turn w/o Ollama).
provider_factory: Callable[[], object] | None = None

# The agent's own repo root (…/frontend/backend/sessions.py → repo root). A session
# is never allowed to be scoped here — the audited target stays strictly external.
_AGENT_ROOT = Path(__file__).resolve().parents[2]


class Session:
    def __init__(self, chat: ChatSession, loop: OrchestratorLoop) -> None:
        self.chat = chat
        self.loop = loop


class SessionManager:
    def __init__(self, memory: EpisodicMemory) -> None:
        self._memory = memory
        self._sessions: dict[str, Session] = {}

    def start(self, project_path: str, project_id: str | None = None) -> Session:
        # The target is ALWAYS an explicit, existing, EXTERNAL folder. No silent
        # fallback to "." — that would scope the session at the agent's own repo,
        # letting it read/write its own tree and mixing target code into the agent
        # (see memory feedback_no_target_code_in_agent).
        if not project_path or not str(project_path).strip():
            raise ValueError("project path is required (the external target folder)")
        p = Path(project_path).expanduser()
        if not p.is_dir():
            raise ValueError(f"project path is not an existing directory: {project_path}")
        audit_root = p.resolve()
        if audit_root == _AGENT_ROOT or _AGENT_ROOT in audit_root.parents:
            raise ValueError("project path must be an EXTERNAL target, not the agent repo itself")
        pid = project_id or audit_root.name
        principal = Principal(user_id="ui", platform="cli", project_id=pid)
        chat = ChatSession(principal=principal)
        save_session(chat, self._memory)

        loop = self._build_loop(chat, principal, audit_root)
        s = Session(chat, loop)
        self._sessions[chat.session_id] = s
        return s

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def _build_loop(self, chat: ChatSession, principal: Principal, audit_root: Path) -> OrchestratorLoop:
        audit_session = AuditSession(
            principal=principal, audit_input=AuditInput(path=audit_root, principal=principal),
        )
        if provider_factory is not None:
            provider = provider_factory()
        else:
            provider = ChatReasoningProvider(
                local=CONFIG.local_client(), session=audit_session, relay_dir=config.relay_root,
                system_prompt=AUDIT_CHAT_SYSTEM, signal_from=signal_from,
                domain_escalation=domain_escalation,
            )
        return OrchestratorLoop(
            audit_session, self._memory, audit_root,
            pack=AUDIT_PACK, reasoning_provider=provider,
            confirmations_dir=config.confirmations_root,
            event_sink=events.make_sink(chat.session_id),
        )
