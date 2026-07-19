from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import UUID

from core.services.agent_run_service import AgentRunService
from core.services.conversation_service import ConversationService
from core.services.keycloak_auth_service import KeycloakUser
from core.services.llm_logging import reset_current_run_id
from core.services.observability_service import ObservabilityService

if TYPE_CHECKING:
    from core.services.agent_service import AgentService


@dataclass
class ChatReply:
    reply: str
    role: str  # message role — always "assistant" for chat replies
    conversation_id: str
    tool_trace: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str | None = None
    latency_ms: int | None = None
    run_id: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatService:
    """Chat entrypoint — persists turns and delegates to the LangGraph agent."""

    def __init__(
        self,
        agent: AgentService | None = None,
        observability: ObservabilityService | None = None,
        conversations: ConversationService | None = None,
        runs: AgentRunService | None = None,
    ) -> None:
        self._agent = agent
        self.observability = observability or ObservabilityService()
        self.conversations = conversations or ConversationService()
        self.runs = runs or AgentRunService()

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
        conversation = self.conversations.ensure_for_user(user, conversation_id)
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
        run = self.runs.start(
            user,
            user_message=message.strip(),
            conversation=conversation,
            trace_id=trace.trace_id,
        )
        run_token = self.runs.bind(run)
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
            self.runs.record_tools(run, result.tool_trace)
            self.observability.record_tools(trace, result.tool_trace)
            self.observability.finish(
                trace,
                reply=result.reply,
                started_perf=started,
            )
            finished = self.runs.finish(
                run,
                assistant_reply=result.reply,
                latency_ms=trace.latency_ms,
            )
            return ChatReply(
                reply=result.reply,
                role="assistant",
                conversation_id=str(conversation.id),
                tool_trace=result.tool_trace,
                trace_id=trace.trace_id,
                latency_ms=trace.latency_ms,
                run_id=str(finished.id),
                prompt_tokens=finished.prompt_tokens,
                completion_tokens=finished.completion_tokens,
                total_tokens=finished.total_tokens,
            )
        except Exception as exc:
            self.observability.finish(
                trace,
                error=str(exc),
                started_perf=started,
            )
            self.runs.finish(
                run,
                error=str(exc),
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            raise
        finally:
            reset_current_run_id(run_token)
