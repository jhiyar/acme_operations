from django.test import TestCase

from core.models import Conversation, Message
from core.services.chat_service import ChatService
from core.services.conversation_service import ConversationService
from core.services.keycloak_auth_service import KeycloakUser
from unittest.mock import MagicMock


def make_user(username: str = "support") -> KeycloakUser:
    return KeycloakUser(
        sub=f"sub-{username}",
        username=username,
        email=f"{username}@example.com",
        roles=["support_user"],
    )


class ConversationServiceTests(TestCase):
    def test_create_list_and_detail(self) -> None:
        user = make_user()
        service = ConversationService()
        conversation = service.create(user, title="")
        service.append_exchange(
            conversation,
            user_message="What is Contoso?",
            assistant_reply="Contoso Ltd is a customer.",
            tool_trace=[{"tool": "get_customer_profile"}],
        )

        listed = service.list_for_user(user)
        self.assertEqual(len(listed), 1)
        detail = service.to_detail(listed[0])
        self.assertEqual(detail["title"], "What is Contoso?")
        self.assertEqual(len(detail["messages"]), 2)
        self.assertEqual(detail["messages"][0]["role"], "user")

    def test_owner_isolation(self) -> None:
        service = ConversationService()
        mine = service.create(make_user("a"))
        other = make_user("b")
        with self.assertRaises(Conversation.DoesNotExist):
            service.get_for_user(mine.id, other)


class ChatPersistsConversationTests(TestCase):
    def test_chat_creates_conversation_and_messages(self) -> None:
        user = make_user("admin")
        fake_agent = MagicMock()
        fake_agent.run.return_value = MagicMock(
            reply="Hello",
            tool_trace=[],
        )
        reply = ChatService(agent=fake_agent).call("hi there", user)
        conversation = Conversation.objects.get(pk=reply.conversation_id)
        self.assertEqual(conversation.owner_sub, user.sub)
        self.assertEqual(conversation.title, "hi there")
        self.assertEqual(Message.objects.filter(conversation=conversation).count(), 2)
        fake_agent.run.assert_called_once()
        self.assertEqual(
            fake_agent.run.call_args.kwargs["session_id"],
            str(conversation.id),
        )
