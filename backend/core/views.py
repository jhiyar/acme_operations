from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response

from core.authentication import KeycloakJWTAuthentication
from core.models import AgentRun, Conversation
from core.permissions import CanUseAssistant, IsAdmin, IsAuthenticatedKeycloak
from core.serializers import (
    AgentToolCallSerializer,
    ChatRequestSerializer,
    UserPatchSerializer,
    UserWriteSerializer,
)
from core.services import AgentToolService, ChatService, HealthService, KeycloakAuthService
from core.services.agent_run_service import AgentRunService
from core.services.conversation_service import ConversationService
from core.services.keycloak_admin_service import KeycloakAdminError, KeycloakAdminService


class HealthView(generics.GenericAPIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request: Request) -> Response:
        from core.services.memory_service import MemoryService

        result = HealthService().check()
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
        try:
            conversation = service.get_for_user(conversation_id, request.user)
        except Conversation.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
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
                "run_id": result.run_id,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "total_tokens": result.total_tokens,
            }
        )


class AgentRunListView(generics.GenericAPIView):
    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [IsAuthenticatedKeycloak, IsAdmin]

    def get(self, request: Request) -> Response:
        try:
            limit = int(request.query_params.get("limit", 50))
        except (TypeError, ValueError):
            limit = 50
        service = AgentRunService()
        runs = service.list_runs(limit=limit)
        return Response(
            {
                "count": len(runs),
                "runs": [service.to_summary(run) for run in runs],
            }
        )


class AgentRunDetailView(generics.GenericAPIView):
    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [IsAuthenticatedKeycloak, IsAdmin]

    def get(self, request: Request, run_id) -> Response:
        service = AgentRunService()
        try:
            run = service.get_run(run_id)
        except AgentRun.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(service.to_detail(run))


class AgentToolsView(generics.GenericAPIView):
    """List agent tool specs (debug / eval harness)."""

    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [IsAuthenticatedKeycloak, CanUseAssistant]

    def get(self, request: Request) -> Response:
        return Response({"tools": AgentToolService().tool_specs()})


class AgentToolCallView(generics.GenericAPIView):
    """
    Invoke a single agent tool by name (debug / eval).

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


def _keycloak_admin_error_response(exc: KeycloakAdminError) -> Response:
    code = exc.status_code
    if code not in {
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_404_NOT_FOUND,
        status.HTTP_409_CONFLICT,
        status.HTTP_503_SERVICE_UNAVAILABLE,
    }:
        code = status.HTTP_400_BAD_REQUEST
    return Response({"detail": exc.message}, status=code)


class UserListCreateView(generics.GenericAPIView):
    """Admin-only Keycloak user directory."""

    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [IsAuthenticatedKeycloak, IsAdmin]

    def get(self, request: Request) -> Response:
        try:
            users = KeycloakAdminService().list_users()
        except KeycloakAdminError as exc:
            return _keycloak_admin_error_response(exc)
        return Response({"count": len(users), "users": users})

    def post(self, request: Request) -> Response:
        serializer = UserWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = KeycloakAdminService().create_user(**serializer.validated_data)
        except KeycloakAdminError as exc:
            return _keycloak_admin_error_response(exc)
        return Response({"created": True, "user": user}, status=status.HTTP_201_CREATED)


class UserDetailView(generics.GenericAPIView):
    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [IsAuthenticatedKeycloak, IsAdmin]

    def get(self, request: Request, user_id: str) -> Response:
        try:
            user = KeycloakAdminService().get_user(user_id)
        except KeycloakAdminError as exc:
            return _keycloak_admin_error_response(exc)
        return Response(user)

    def patch(self, request: Request, user_id: str) -> Response:
        serializer = UserPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = KeycloakAdminService().update_user(
                user_id, **serializer.validated_data
            )
        except KeycloakAdminError as exc:
            return _keycloak_admin_error_response(exc)
        return Response({"updated": True, "user": user})

    def delete(self, request: Request, user_id: str) -> Response:
        if user_id == getattr(request.user, "sub", None):
            return Response(
                {"detail": "You cannot delete your own account"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            KeycloakAdminService().delete_user(user_id)
        except KeycloakAdminError as exc:
            return _keycloak_admin_error_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)
