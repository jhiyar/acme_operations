from __future__ import annotations

import json
from typing import Any, Callable

from core.permissions import can_create_next_action
from core.services.keycloak_auth_service import KeycloakUser
from core.services.llm import get_llm_client
from core.services.llm.base import LlmClient, LlmMessage
from issues.models import Issue, IssueUpdate, NextAction
from issues.services import CustomerService, IssueService

SUMMARISE_SYSTEM = (
    "You are an operations assistant. Summarise the issue history clearly and factually. "
    "Cover status, priority, assignment, key updates, and outstanding next actions. "
    "Do not invent details that are not in the provided context."
)

RECOMMEND_SYSTEM = (
    "You are an operations assistant. Recommend a single concrete next action for this issue. "
    "Be specific and actionable in 1-3 sentences. Do not invent facts; ground the "
    "recommendation in the provided history. Return only the recommendation text."
)


class AgentToolService:
    """
    Tools the LLM agent can invoke.

    Each public method is one tool. Views/agents stay thin and call these.
    """

    def __init__(
        self,
        customer_service: CustomerService | None = None,
        issue_service: IssueService | None = None,
        llm: LlmClient | None = None,
    ) -> None:
        self.customers = customer_service or CustomerService()
        self.issues = issue_service or IssueService()
        self._llm = llm

    @property
    def llm(self) -> LlmClient:
        if self._llm is None:
            self._llm = get_llm_client()
        return self._llm

    def get_customer_profile(
        self,
        customer_name: str,
        user: KeycloakUser | None = None,
    ) -> dict[str, Any]:
        customer = self.customers.get_by_name(customer_name)
        if not customer:
            return {"found": False, "customer_name": customer_name}
        return {"found": True, "customer": self.customers.to_dict(customer)}

    def get_open_issues_for_customer(
        self,
        customer_name: str,
        user: KeycloakUser | None = None,
    ) -> dict[str, Any]:
        customer = self.customers.get_by_name(customer_name)
        if not customer:
            return {
                "found": False,
                "customer_name": customer_name,
                "issues": [],
            }
        issues = self.issues.open_issues_for_customer(customer_name, user=user)
        return {
            "found": True,
            "customer": self.customers.to_dict(customer),
            "open_issue_count": len(issues),
            "issues": issues,
        }

    def summarise_issue_history(
        self,
        issue_id: int,
        user: KeycloakUser | None = None,
    ) -> dict[str, Any]:
        issue = self._get_issue(issue_id, user)
        if not issue:
            return {"found": False, "issue_id": issue_id}

        context = self._issue_context(issue)
        timeline = context["timeline"]
        response = self.llm.complete(
            [LlmMessage(role="user", content=json.dumps(context, default=str))],
            system=SUMMARISE_SYSTEM,
        )
        return {
            "found": True,
            "issue_id": issue.id,
            "summary": response.text,
            "timeline": timeline,
            "issue": self.issues.to_dict(issue, include_history=True),
        }

    def create_next_action(
        self,
        issue_id: int,
        user: KeycloakUser,
    ) -> dict[str, Any]:
        if not can_create_next_action(user):
            return {
                "created": False,
                "error": "Only support_user or admin can create next actions",
            }

        issue = self._get_issue(issue_id, user)
        if not issue:
            return {"created": False, "error": f"Issue #{issue_id} not found or not visible"}

        context = self._issue_context(issue)
        response = self.llm.complete(
            [LlmMessage(role="user", content=json.dumps(context, default=str))],
            system=RECOMMEND_SYSTEM,
        )
        text = response.text.strip()
        if not text:
            return {"created": False, "error": "LLM returned an empty recommendation"}

        action = NextAction.objects.create(
            issue=issue,
            summary=text,
            recommended_by=user.username,
            status=NextAction.Status.PENDING,
        )
        IssueUpdate.objects.create(
            issue=issue,
            author=user.username,
            body=f"Recommended next action: {text}",
        )
        return {
            "created": True,
            "next_action": {
                "id": action.id,
                "issue_id": issue.id,
                "summary": action.summary,
                "recommended_by": action.recommended_by,
                "status": action.status,
            },
        }

    def invoke(
        self,
        tool: str,
        args: dict[str, Any],
        user: KeycloakUser,
    ) -> dict[str, Any]:
        handlers: dict[str, Callable[..., dict[str, Any]]] = {
            "get_customer_profile": lambda: self.get_customer_profile(
                str(args.get("customer_name", "")),
                user=user,
            ),
            "get_open_issues_for_customer": lambda: self.get_open_issues_for_customer(
                str(args.get("customer_name", "")),
                user=user,
            ),
            "summarise_issue_history": lambda: self.summarise_issue_history(
                int(args["issue_id"]),
                user=user,
            ),
            "create_next_action": lambda: self.create_next_action(
                int(args["issue_id"]),
                user=user,
            ),
        }
        if tool not in handlers:
            raise ValueError(f"Unknown tool: {tool}")
        try:
            return handlers[tool]()
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(str(exc)) from exc

    def tool_specs(self) -> list[dict[str, Any]]:
        """Machine-readable tool list for the agent and debug HTTP API."""
        return [
            {
                "name": "get_customer_profile",
                "description": "Retrieve the customer profile using the customer name",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_name": {
                            "type": "string",
                            "description": "Exact or case-insensitive customer name",
                        },
                    },
                    "required": ["customer_name"],
                },
            },
            {
                "name": "get_open_issues_for_customer",
                "description": "Retrieve all open issues for a given customer",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "customer_name": {
                            "type": "string",
                            "description": "Exact or case-insensitive customer name",
                        },
                    },
                    "required": ["customer_name"],
                },
            },
            {
                "name": "summarise_issue_history",
                "description": (
                    "Summarise the history of a specific issue using an LLM grounded "
                    "in the issue updates and next actions"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_id": {
                            "type": "integer",
                            "description": "Issue primary key",
                        },
                    },
                    "required": ["issue_id"],
                },
            },
            {
                "name": "create_next_action",
                "description": (
                    "Generate an LLM recommendation for the next action on an issue "
                    "and persist it. Only support_user or admin may succeed."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_id": {
                            "type": "integer",
                            "description": "Issue primary key",
                        },
                    },
                    "required": ["issue_id"],
                },
            },
        ]

    def _issue_context(self, issue: Issue) -> dict[str, Any]:
        updates = list(issue.updates.all())
        actions = list(issue.next_actions.all())
        timeline = [
            f"[{u.created_at.date()}] {u.author}: {u.body}" for u in updates
        ]
        return {
            "issue": {
                "id": issue.id,
                "title": issue.title,
                "description": issue.description,
                "status": issue.status,
                "priority": issue.priority,
                "assigned_to": issue.assigned_to,
                "customer": issue.customer.name,
            },
            "updates": [
                {
                    "author": u.author,
                    "body": u.body,
                    "created_at": u.created_at.isoformat(),
                }
                for u in updates
            ],
            "next_actions": [
                {
                    "summary": a.summary,
                    "recommended_by": a.recommended_by,
                    "status": a.status,
                    "created_at": a.created_at.isoformat(),
                }
                for a in actions
            ],
            "timeline": timeline,
        }

    def _get_issue(self, issue_id: int, user: KeycloakUser | None) -> Issue | None:
        if user:
            return self.issues.get_for_user(user, issue_id)
        return (
            Issue.objects.select_related("customer")
            .prefetch_related("updates", "next_actions")
            .filter(pk=issue_id)
            .first()
        )
