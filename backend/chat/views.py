from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response

from chat.serializers import ChatRequestSerializer
from core.authentication import KeycloakJWTAuthentication
from core.models import Conversation
from core.permissions import CanUseAssistant, IsAuthenticatedKeycloak
from core.services import ChatService
from core.services.conversation_service import ConversationService


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
