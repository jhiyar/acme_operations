from django.test import TestCase
from unittest.mock import MagicMock

from core.models import AgentRun, LlmCall, ToolCall
from core.services.agent_run_service import AgentRunService
from core.services.chat_service import ChatService
from core.services.keycloak_auth_service import KeycloakUser
from core.services.llm_logging import record_llm_call, set_current_run_id


def make_user(username: str = "admin", *roles: str) -> KeycloakUser:
    return KeycloakUser(
        sub=f"sub-{username}",
        username=username,
        email=f"{username}@example.com",
        roles=list(roles) or ["admin"],
    )


class AgentRunPersistenceTests(TestCase):
    def test_chat_persists_run_tools_and_llm_calls(self) -> None:
        user = make_user("admin", "admin")
        fake_agent = MagicMock()
        fake_agent.run.return_value = MagicMock(
            reply="Hello",
            tool_trace=[{"tool": "get_customer_profile", "args": {"customer_name": "Contoso"}, "result": "{}"}],
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            llm_call_count=1,
        )
        reply = ChatService(agent=fake_agent).call("hi", user)
        run = AgentRun.objects.get(pk=reply.run_id)
        self.assertEqual(run.username, "admin")
        self.assertEqual(run.tool_count, 1)
        self.assertEqual(ToolCall.objects.filter(run=run).count(), 1)
        self.assertEqual(run.assistant_reply, "Hello")

    def test_record_llm_call_links_to_current_run(self) -> None:
        user = make_user()
        run = AgentRunService().start(user, user_message="test")
        token = set_current_run_id(run.id)
        try:
            record_llm_call(
                provider="anthropic",
                model="claude-test",
                prompt_tokens=3,
                completion_tokens=2,
                total_tokens=5,
                purpose="summarise_issue_history",
            )
        finally:
            from core.services.llm_logging import reset_current_run_id

            reset_current_run_id(token)

        self.assertEqual(LlmCall.objects.filter(run=run).count(), 1)
        run.refresh_from_db()
        self.assertEqual(run.total_tokens, 5)
        self.assertEqual(run.llm_call_count, 1)
