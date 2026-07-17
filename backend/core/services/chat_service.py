from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.services.agent_service import AgentService
from core.services.keycloak_auth_service import KeycloakUser


@dataclass
class ChatReply:
    reply: str
    role: str
    tool_trace: list[dict[str, Any]] = field(default_factory=list)


class ChatService:
    """Chat entrypoint — delegates to the LangGraph tool-calling agent."""

    def __init__(self, agent: AgentService | None = None) -> None:
        self.agent = agent or AgentService()

    def call(self, message: str, user: KeycloakUser) -> ChatReply:
        primary_role = user.roles[0] if user.roles else "user"
        result = self.agent.run(message.strip(), user)
        return ChatReply(
            reply=result.reply,
            role=primary_role,
            tool_trace=result.tool_trace,
        )
