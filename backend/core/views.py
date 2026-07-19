from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response

from core.authentication import (
    CanUseAssistant,
    IsAuthenticatedKeycloak,
    KeycloakJWTAuthentication,
)
from core.models import Conversation
from core.serializers import AgentToolCallSerializer, ChatRequestSerializer
from core.services import AgentToolService, ChatService, HealthService, KeycloakAuthService
from core.services.conversation_service import ConversationService


class HealthView(generics.GenericAPIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: Request) -> Response:
        from core.services.memory_service import MemoryService

        result = HealthService().call()
        result["keycloak"] = KeycloakAuthService().health()
        memory = MemoryService()
        result["redis"] = {
            "status": "ok" if memory.enabled else "unavailable",
        }
        return Response(result)


class MeView(generics.GenericAPIView):
    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [IsAuthenticatedKeycloak]

    def get(self, request: Request) -> Response:
        user = request.user
        return Response(
            {
                "sub": user.sub,
                "username": user.username,
                "email": user.email,
                "roles": user.roles,
            }
        )


class ConversationListCreateView(generics.GenericAPIView):
    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [IsAuthenticatedKeycloak, CanUseAssistant]

    def get(self, request: Request) -> Response:
        service = ConversationService()
        conversations = service.list_for_user(request.user)
        return Response(
            {
                "count": len(conversations),
                "conversations": [service.to_summary(item) for item in conversations],
            }
        )

    def post(self, request: Request) -> Response:
        conversation = ConversationService().create(request.user)
        return Response(
            ConversationService().to_detail(conversation),
            status=status.HTTP_201_CREATED,
        )


class ConversationDetailView(generics.GenericAPIView):
    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [IsAuthenticatedKeycloak, CanUseAssistant]

    def get(self, request: Request, conversation_id) -> Response:
        service = ConversationService()
        conversation = get_object_or_404(
            Conversation,
            pk=conversation_id,
            owner_sub=request.user.sub,
        )
        return Response(service.to_detail(conversation))

    def delete(self, request: Request, conversation_id) -> Response:
        try:
            ConversationService().delete_for_user(conversation_id, request.user)
        except Conversation.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChatView(generics.GenericAPIView):
    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [IsAuthenticatedKeycloak, CanUseAssistant]
    serializer_class = ChatRequestSerializer

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session_id = (serializer.validated_data.get("session_id") or "").strip() or None
        try:
            result = ChatService().call(
                serializer.validated_data["message"],
                request.user,
                conversation_id=serializer.validated_data.get("conversation_id"),
                session_id=session_id,
            )
        except Conversation.DoesNotExist:
            return Response(
                {"detail": "Conversation not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except RuntimeError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as exc:  # noqa: BLE001 — surface agent failures to the client
            return Response(
                {"detail": f"Assistant failed: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(
            {
                "reply": result.reply,
                "role": result.role,
                "conversation_id": result.conversation_id,
                "tool_trace": result.tool_trace,
                "trace_id": result.trace_id,
                "latency_ms": result.latency_ms,
            }
        )


class AgentToolsView(generics.GenericAPIView):
    """List available agent tools (for UI/debug and future agent wiring)."""

    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [IsAuthenticatedKeycloak, CanUseAssistant]

    def get(self, request: Request) -> Response:
        return Response({"tools": AgentToolService().tool_specs()})


class AgentToolCallView(generics.GenericAPIView):
    """
    Invoke a single agent tool by name.

    Body: { "tool": "get_open_issues_for_customer", "args": { "customer_name": "..." } }
    """

    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [IsAuthenticatedKeycloak, CanUseAssistant]
    serializer_class = AgentToolCallSerializer

    def post(self, request: Request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tool = serializer.validated_data["tool"]
        args = serializer.validated_data["args"]
        try:
            result = AgentToolService().invoke(tool, args, request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"tool": tool, "result": result})
