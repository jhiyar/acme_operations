from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from core.services.agent_service import AgentService
from core.services.agent_tool_service import AgentToolService
from core.services.chat_service import ChatService
from core.services.keycloak_auth_service import KeycloakUser
from core.services.llm.anthropic_llm_service import AnthropicLlmService
from core.services.llm.base import LlmClient, LlmMessage, LlmResponse
from core.services.llm.openai_llm_service import OpenAiCompatibleLlmService
from issues.models import Customer, Issue, IssueUpdate, NextAction


def make_user(username: str, *roles: str) -> KeycloakUser:
    return KeycloakUser(
        sub=f"sub-{username}",
        username=username,
        email=f"{username}@example.com",
        roles=list(roles),
    )


class FakeLlm(LlmClient):
    def __init__(self, text: str = "LLM output") -> None:
        self.text = text
        self.calls: list[tuple[list[LlmMessage], str | None]] = []

    def complete(
        self,
        messages: list[LlmMessage],
        *,
        system: str | None = None,
    ) -> LlmResponse:
        self.calls.append((messages, system))
        return LlmResponse(text=self.text)


class AgentToolServiceTests(TestCase):
    def setUp(self) -> None:
        self.llm = FakeLlm("Concise summary of the issue.")
        self.service = AgentToolService(llm=self.llm)
        self.customer = Customer.objects.create(name="Contoso Ltd", tier="premium")
        self.issue = Issue.objects.create(
            customer=self.customer,
            title="Alert noise",
            description="False positives",
            status=Issue.Status.OPEN,
            priority=Issue.Priority.CRITICAL,
            assigned_to="support",
        )
        IssueUpdate.objects.create(
            issue=self.issue,
            author="support",
            body="Rolled thresholds back",
        )

    def test_get_customer_profile_found(self) -> None:
        result = self.service.get_customer_profile("contoso ltd")
        self.assertTrue(result["found"])
        self.assertEqual(result["customer"]["name"], "Contoso Ltd")

    def test_get_customer_profile_missing(self) -> None:
        result = self.service.get_customer_profile("Unknown")
        self.assertFalse(result["found"])

    def test_get_open_issues_for_customer(self) -> None:
        result = self.service.get_open_issues_for_customer("Contoso Ltd")
        self.assertTrue(result["found"])
        self.assertEqual(result["open_issue_count"], 1)

    def test_summarise_issue_history_uses_llm(self) -> None:
        user = make_user("support", "support_user")
        result = self.service.summarise_issue_history(self.issue.id, user=user)
        self.assertTrue(result["found"])
        self.assertEqual(result["summary"], "Concise summary of the issue.")
        self.assertEqual(len(self.llm.calls), 1)
        self.assertIn("Summarise", self.llm.calls[0][1] or "")

    def test_create_next_action_persists_llm_recommendation(self) -> None:
        self.llm.text = "Schedule vendor bridge call this week."
        user = make_user("support", "support_user")
        result = self.service.create_next_action(self.issue.id, user=user)
        self.assertTrue(result["created"])
        self.assertEqual(
            result["next_action"]["summary"],
            "Schedule vendor bridge call this week.",
        )
        self.assertEqual(NextAction.objects.count(), 1)
        self.assertTrue(
            IssueUpdate.objects.filter(
                issue=self.issue,
                body__startswith="Recommended next action:",
            ).exists()
        )

    def test_create_next_action_rbac_denied_for_sales(self) -> None:
        user = make_user("sales", "sales_user")
        result = self.service.create_next_action(self.issue.id, user=user)
        self.assertFalse(result["created"])
        self.assertIn("support_user or admin", result["error"])
        self.assertEqual(NextAction.objects.count(), 0)
        self.assertEqual(len(self.llm.calls), 0)

    def test_invoke_unknown_tool(self) -> None:
        user = make_user("admin", "admin")
        with self.assertRaises(ValueError):
            self.service.invoke("nope", {}, user)


class AgentServiceTests(TestCase):
    def test_run_extracts_reply_and_tool_trace(self) -> None:
        class FakeGraph:
            def invoke(self, *_args, **_kwargs):
                return {
                    "messages": [
                        HumanMessage(content="Who is Contoso?"),
                        AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "name": "get_customer_profile",
                                    "args": {"customer_name": "Contoso Ltd"},
                                    "id": "call-1",
                                    "type": "tool_call",
                                }
                            ],
                        ),
                        ToolMessage(
                            content='{"found": true, "customer": {"name": "Contoso Ltd"}}',
                            tool_call_id="call-1",
                            name="get_customer_profile",
                        ),
                        AIMessage(content="Contoso Ltd is a premium customer."),
                    ]
                }

        user = make_user("admin", "admin")
        service = AgentService(chat_model=MagicMock())
        with patch(
            "core.services.agent_service.create_react_agent",
            return_value=FakeGraph(),
        ):
            result = service.run("Who is Contoso?", user)

        self.assertEqual(result.reply, "Contoso Ltd is a premium customer.")
        self.assertEqual(len(result.tool_trace), 1)
        self.assertEqual(result.tool_trace[0]["tool"], "get_customer_profile")
        self.assertIn("found", result.tool_trace[0]["result"])


class ChatServiceTests(TestCase):
    def test_call_delegates_to_agent(self) -> None:
        user = make_user("admin", "admin")
        fake_agent = MagicMock()
        fake_agent.run.return_value = MagicMock(
            reply="Hello from agent",
            tool_trace=[{"tool": "get_customer_profile"}],
        )
        reply = ChatService(agent=fake_agent).call("hi", user)
        self.assertEqual(reply.reply, "Hello from agent")
        self.assertEqual(reply.role, "admin")
        self.assertEqual(reply.tool_trace[0]["tool"], "get_customer_profile")
        self.assertTrue(reply.conversation_id)
        fake_agent.run.assert_called_once()
        self.assertIsNotNone(reply.trace_id)
        self.assertIsNotNone(reply.latency_ms)


class LlmClientFormattingTests(SimpleTestCase):
    def test_anthropic_complete_formats_messages(self) -> None:
        fake_client = MagicMock()
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "hello"
        fake_client.messages.create.return_value = MagicMock(
            content=[text_block],
            id="msg_1",
        )
        service = AnthropicLlmService(api_key="test", model="claude-test", client=fake_client)
        result = service.complete(
            [LlmMessage(role="user", content="ping")],
            system="be brief",
        )
        self.assertEqual(result.text, "hello")
        kwargs = fake_client.messages.create.call_args.kwargs
        self.assertEqual(kwargs["system"], "be brief")
        self.assertEqual(kwargs["messages"][0]["content"], "ping")

    def test_openai_complete_formats_messages(self) -> None:
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="pong"))],
            id="chat_1",
        )
        service = OpenAiCompatibleLlmService(
            api_key="test",
            model="gpt-test",
            base_url="http://localhost:11434/v1",
            client=fake_client,
        )
        result = service.complete(
            [LlmMessage(role="user", content="ping")],
            system="be brief",
        )
        self.assertEqual(result.text, "pong")
        kwargs = fake_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["messages"][0]["role"], "system")
        self.assertEqual(kwargs["messages"][1]["content"], "ping")
