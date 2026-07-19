from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from core.models import Conversation, Message
from core.services.keycloak_auth_service import KeycloakUser


def _title_from_message(message: str) -> str:
    cleaned = " ".join(message.strip().split())
    if len(cleaned) <= 72:
        return cleaned
    return f"{cleaned[:69].rstrip()}…"


class ConversationService:
    """Durable chat conversations owned by a Keycloak subject."""

    def list_for_user(self, user: KeycloakUser) -> list[Conversation]:
        return list(Conversation.objects.filter(owner_sub=user.sub))

    def get_for_user(self, conversation_id: UUID | str, user: KeycloakUser) -> Conversation:
        return Conversation.objects.get(pk=conversation_id, owner_sub=user.sub)

    def create(self, user: KeycloakUser, *, title: str = "") -> Conversation:
        return Conversation.objects.create(owner_sub=user.sub, title=title)

    def delete_for_user(self, conversation_id: UUID | str, user: KeycloakUser) -> None:
        conversation = self.get_for_user(conversation_id, user)
        conversation.delete()

    def ensure_for_user(
        self,
        user: KeycloakUser,
        conversation_id: UUID | str | None,
    ) -> Conversation:
        if conversation_id:
            return self.get_for_user(conversation_id, user)
        return self.create(user)

    @transaction.atomic
    def append_exchange(
        self,
        conversation: Conversation,
        *,
        user_message: str,
        assistant_reply: str,
        tool_trace: list[dict[str, Any]] | None = None,
    ) -> tuple[Message, Message]:
        if not conversation.title:
            conversation.title = _title_from_message(user_message)

        user_row = Message.objects.create(
            conversation=conversation,
            role=Message.Role.USER,
            content=user_message,
        )
        assistant_row = Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content=assistant_reply,
            tool_trace=tool_trace or [],
        )
        conversation.updated_at = timezone.now()
        conversation.save(update_fields=["title", "updated_at"])
        return user_row, assistant_row

    def to_summary(self, conversation: Conversation) -> dict[str, Any]:
        return {
            "id": str(conversation.id),
            "title": conversation.title or "New conversation",
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "message_count": conversation.messages.count(),
        }

    def to_detail(self, conversation: Conversation) -> dict[str, Any]:
        messages = [
            {
                "id": str(message.id),
                "role": message.role,
                "content": message.content,
                "tool_trace": message.tool_trace,
                "created_at": message.created_at.isoformat(),
            }
            for message in conversation.messages.all()
        ]
        return {
            **self.to_summary(conversation),
            "messages": messages,
        }
