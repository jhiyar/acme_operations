from core.services.health_service import HealthService
from core.services.keycloak_auth_service import KeycloakAuthService, KeycloakUser

__all__ = [
    "AgentService",
    "AgentToolService",
    "ChatService",
    "HealthService",
    "KeycloakAuthService",
    "KeycloakUser",
]


def __getattr__(name: str):
    if name == "AgentService":
        from core.services.agent_service import AgentService

        return AgentService
    if name == "AgentToolService":
        from core.services.agent_tool_service import AgentToolService

        return AgentToolService
    if name == "ChatService":
        from core.services.chat_service import ChatService

        return ChatService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
