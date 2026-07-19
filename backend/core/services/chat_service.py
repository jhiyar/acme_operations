from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from core.services.keycloak_auth_service import KeycloakUser
from core.services.observability_service import ObservabilityService

if TYPE_CHECKING:
    from core.services.agent_service import AgentService


@dataclass
class ChatReply:
    reply: str
    role: str
    tool_trace: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str | None = None
    latency_ms: int | None = None


class ChatService:
    """Chat entrypoint — delegates to the LangGraph tool-calling agent."""

    def __init__(
        self,
        agent: AgentService | None = None,
        observability: ObservabilityService | None = None,
    ) -> None:
        self._agent = agent
        self.observability = observability or ObservabilityService()

    @property
    def agent(self):
        if self._agent is None:
            from core.services.agent_service import AgentService

            self._agent = AgentService()
        return self._agent

    def call(
        self,
        message: str,
        user: KeycloakUser,
        *,
        session_id: str | None = None,
    ) -> ChatReply:
        primary_role = user.roles[0] if user.roles else "user"
        started = time.perf_counter()
        trace = self.observability.start(
            user=user.username,
            message=message,
            meta={"roles": user.roles, "session_id": session_id},
        )
        try:
            result = self.agent.run(
                message.strip(),
                user,
                session_id=session_id,
            )
            self.observability.record_tools(trace, result.tool_trace)
            self.observability.finish(
                trace,
                reply=result.reply,
                started_perf=started,
            )
            return ChatReply(
                reply=result.reply,
                role=primary_role,
                tool_trace=result.tool_trace,
                trace_id=trace.trace_id,
                latency_ms=trace.latency_ms,
            )
        except Exception as exc:
            self.observability.finish(
                trace,
                error=str(exc),
                started_perf=started,
            )
            raise
