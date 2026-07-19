from django.test import TestCase, override_settings

from core.models import Conversation, Message
from core.services.agent_service import AgentService, _truncate_turn
from core.services.keycloak_auth_service import KeycloakUser
from core.services.memory_service import MemoryService


def make_user() -> KeycloakUser:
    return KeycloakUser(
        sub="sub-support",
        username="support",
        email="support@example.com",
        roles=["support_user"],
    )


class AgentHistoryTests(TestCase):
    def test_truncate_turn(self) -> None:
        self.assertEqual(_truncate_turn("short", 100), "short")
        self.assertTrue(_truncate_turn("x" * 50, 20).endswith("…"))
        self.assertEqual(len(_truncate_turn("x" * 50, 20)), 20)

    @override_settings(AGENT_HISTORY_MAX_TURNS=4, AGENT_HISTORY_MAX_CHARS_PER_TURN=40)
    def test_prefers_postgres_conversation_history(self) -> None:
        user = make_user()
        conversation = Conversation.objects.create(owner_sub=user.sub, title="Northwind")
        Message.objects.create(
            conversation=conversation,
            role=Message.Role.USER,
            content="what issues does Northwind have?",
        )
        Message.objects.create(
            conversation=conversation,
            role=Message.Role.ASSISTANT,
            content="1. Issue #16 tracking\n2. Issue #17 invoice " + ("detail " * 40),
        )

        class EmptyRedis(MemoryService):
            @property
            def enabled(self) -> bool:
                return False

            def get_history(self, *args, **kwargs):
                return []

            def append_turn(self, *args, **kwargs):
                return None

        agent = AgentService(memory=EmptyRedis())
        history = agent._load_history(user.sub, session_id=str(conversation.id))
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertTrue(history[1]["content"].endswith("…"))
        self.assertLessEqual(len(history[1]["content"]), 40)
