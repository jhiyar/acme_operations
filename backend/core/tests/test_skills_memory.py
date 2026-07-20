from __future__ import annotations

from unittest.mock import MagicMock

from django.test import SimpleTestCase, TestCase

from core.services.keycloak_auth_service import KeycloakUser
from core.services.llm.base import LlmClient, LlmMessage, LlmResponse
from core.services.memory_service import MemoryService
from core.services.observability_service import ObservabilityService
from core.skills import CustomerEscalationSummarySkill
from issues.models import Customer, Issue, IssueUpdate


def make_user(username: str, *roles: str) -> KeycloakUser:
    return KeycloakUser(
        sub=f"sub-{username}",
        username=username,
        email=f"{username}@example.com",
        roles=list(roles),
    )


class FakeLlm(LlmClient):
    def __init__(self, text: str) -> None:
        self.text = text

    def complete(
        self,
        messages: list[LlmMessage],
        *,
        system: str | None = None,
        purpose: str = "complete",
    ) -> LlmResponse:
        return LlmResponse(text=self.text)


class MemoryServiceTests(SimpleTestCase):
    def test_append_and_history_with_fake_client(self) -> None:
        store: dict[str, list[str]] = {}
        kv: dict[str, str] = {}

        class FakeRedis:
            def rpush(self, key, value):
                store.setdefault(key, []).append(value)
                return len(store[key])

            def ltrim(self, key, start, end):
                store[key] = store.get(key, [])[start:]
                if end == -1:
                    return True
                store[key] = store[key][: end + 1]
                return True

            def expire(self, key, ttl):
                return True

            def lrange(self, key, start, end):
                return store.get(key, [])

            def ping(self):
                return True

            def get(self, key):
                return kv.get(key)

            def setex(self, key, ttl, value):
                kv[key] = value
                return True

        memory = MemoryService(client=FakeRedis())  # type: ignore[arg-type]
        memory.append_turn("u1", "user", "hello")
        memory.append_turn("u1", "assistant", "hi")
        history = memory.get_history("u1")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")

        key = memory.tool_cache_key(customer_name="contoso", viewer="admin")
        memory.cache_tool_result(
            "get_open_issues_for_customer",
            key,
            {"found": True, "open_issue_count": 1},
        )
        cached = memory.get_cached_tool_result("get_open_issues_for_customer", key)
        self.assertEqual(cached["open_issue_count"], 1)


class OpenIssuesToolCacheTests(TestCase):
    def setUp(self) -> None:
        self.kv: dict[str, str] = {}

        class FakeRedis:
            def __init__(self, store: dict[str, str]) -> None:
                self.store = store

            def ping(self):
                return True

            def get(self, key):
                return self.store.get(key)

            def setex(self, key, ttl, value):
                self.store[key] = value
                return True

            def rpush(self, *args, **kwargs):
                return 0

            def ltrim(self, *args, **kwargs):
                return True

            def expire(self, *args, **kwargs):
                return True

            def lrange(self, *args, **kwargs):
                return []

        self.memory = MemoryService(client=FakeRedis(self.kv))  # type: ignore[arg-type]
        self.customer = Customer.objects.create(name="Contoso Ltd", tier="premium")
        Issue.objects.create(
            customer=self.customer,
            title="Alert noise",
            description="False positives",
            status=Issue.Status.OPEN,
            priority=Issue.Priority.CRITICAL,
            assigned_to="support",
        )

    def test_get_open_issues_uses_redis_tool_cache(self) -> None:
        from core.services.agent_tool_service import AgentToolService

        service = AgentToolService(memory=self.memory)
        user = make_user("admin", "admin")
        first = service.get_open_issues_for_customer("Contoso Ltd", user=user)
        second = service.get_open_issues_for_customer("Contoso Ltd", user=user)
        self.assertTrue(first["found"])
        self.assertNotIn("cache_hit", first)
        self.assertTrue(second["cache_hit"])
        self.assertEqual(second["open_issue_count"], first["open_issue_count"])
        self.assertTrue(any(k.startswith("acme:tool:get_open_issues_for_customer:") for k in self.kv))


class ObservabilityServiceTests(SimpleTestCase):
    def test_finish_records_latency_and_tools(self) -> None:
        obs = ObservabilityService(memory=MemoryService())
        trace = obs.start(user="admin", message="hi")
        obs.record_tools(trace, [{"tool": "get_customer_profile", "args": {}, "result": "{}"}])
        finished = obs.finish(trace, reply="ok", started_perf=0.0)
        self.assertEqual(finished.tool_calls[0]["tool"], "get_customer_profile")
        self.assertIsNotNone(finished.latency_ms)
        self.assertEqual(finished.reply, "ok")


class EscalationSkillTests(TestCase):
    def setUp(self) -> None:
        self.customer = Customer.objects.create(name="Contoso Ltd", tier="premium")
        self.issue = Issue.objects.create(
            customer=self.customer,
            title="Alert noise",
            description="False positives after firmware",
            status=Issue.Status.OPEN,
            priority=Issue.Priority.CRITICAL,
            assigned_to="support",
        )
        IssueUpdate.objects.create(
            issue=self.issue,
            author="support",
            body="Staging thresholds rolled back",
        )
        self.llm = FakeLlm(
            '{"executive_summary":"Critical alert noise","risk_level":"Critical",'
            '"recommended_next_action":"Ship plant profile override",'
            '"missing_information":[],"rationale":"Open critical issue"}'
        )

    def test_skill_runs_multi_step_workflow(self) -> None:
        from core.services.agent_tool_service import AgentToolService

        tools = AgentToolService(llm=self.llm)
        skill = CustomerEscalationSummarySkill(tools=tools, llm=self.llm)
        result = skill.run("Contoso", make_user("support", "support_user"))
        self.assertTrue(result["completed"])
        self.assertEqual(result["result"]["risk_level"], "Critical")
        self.assertIn(self.issue.id, result["inputs"]["summarised_issue_ids"])
