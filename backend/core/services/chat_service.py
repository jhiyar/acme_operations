from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

from core.services.conversation_service import ConversationService
from core.services.keycloak_auth_service import KeycloakUser
from core.services.observability_service import ObservabilityService

if TYPE_CHECKING:
    from core.services.agent_service import AgentService


@dataclass
class ChatReply:
    reply: str
    role: str
    conversation_id: str
    tool_trace: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str | None = None
    latency_ms: int | None = None


class ChatService:
    """Chat entrypoint — persists turns and delegates to the LangGraph agent."""

    def __init__(
        self,
        agent: AgentService | None = None,
        observability: ObservabilityService | None = None,
        conversations: ConversationService | None = None,
    ) -> None:
        self._agent = agent
        self.observability = observability or ObservabilityService()
        self.conversations = conversations or ConversationService()

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
        conversation_id: UUID | str | None = None,
        session_id: str | None = None,
    ) -> ChatReply:
        primary_role = user.roles[0] if user.roles else "user"
        conversation = self.conversations.ensure_for_user(user, conversation_id)
        # Prefer conversation UUID for Redis memory so threads stay isolated.
        effective_session = session_id or str(conversation.id)
        started = time.perf_counter()
        trace = self.observability.start(
            user=user.username,
            message=message,
            meta={
                "roles": user.roles,
                "session_id": effective_session,
                "conversation_id": str(conversation.id),
            },
        )
        try:
            result = self.agent.run(
                message.strip(),
                user,
                session_id=effective_session,
            )
            self.conversations.append_exchange(
                conversation,
                user_message=message.strip(),
                assistant_reply=result.reply,
                tool_trace=result.tool_trace,
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
                conversation_id=str(conversation.id),
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
