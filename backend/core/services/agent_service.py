from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from core.services.agent_tool_service import AgentToolService
from core.services.keycloak_auth_service import KeycloakUser
from core.services.llm import get_chat_model

AGENT_SYSTEM_PROMPT = """You are Acme Operations assistant.
Use tools to look up customers and issues. Never invent customer names, issue IDs, or facts.
If the user asks multiple things, call as many tools as needed and answer every part in your final reply.
For recommended next actions, call create_next_action (it generates and persists the recommendation).
If a tool returns an error (including RBAC), explain it clearly to the user.
"""


class CustomerNameArgs(BaseModel):
    customer_name: str = Field(description="Exact or case-insensitive customer name")


class IssueIdArgs(BaseModel):
    issue_id: int = Field(description="Issue primary key")


@dataclass
class AgentReply:
    reply: str
    tool_trace: list[dict[str, Any]] = field(default_factory=list)


class AgentService:
    """LangGraph ReAct agent that selects and invokes tools dynamically."""

    def __init__(
        self,
        tools: AgentToolService | None = None,
        chat_model: Any | None = None,
    ) -> None:
        self.tools = tools or AgentToolService()
        self._chat_model = chat_model

    @property
    def chat_model(self) -> Any:
        if self._chat_model is None:
            self._chat_model = get_chat_model()
        return self._chat_model

    def run(self, message: str, user: KeycloakUser) -> AgentReply:
        structured_tools = self._build_tools(user)
        agent = create_react_agent(
            self.chat_model,
            structured_tools,
            prompt=AGENT_SYSTEM_PROMPT,
        )
        result = agent.invoke(
            {"messages": [HumanMessage(content=message)]},
            config={"recursion_limit": settings.AGENT_MAX_TOOL_ROUNDS * 2},
        )
        messages = result.get("messages") or []
        return AgentReply(
            reply=self._extract_reply(messages),
            tool_trace=self._extract_tool_trace(messages),
        )

    def _build_tools(self, user: KeycloakUser) -> list[StructuredTool]:
        service = self.tools

        def get_customer_profile(customer_name: str) -> str:
            return json.dumps(
                service.get_customer_profile(customer_name, user=user),
                default=str,
            )

        def get_open_issues_for_customer(customer_name: str) -> str:
            return json.dumps(
                service.get_open_issues_for_customer(customer_name, user=user),
                default=str,
            )

        def summarise_issue_history(issue_id: int) -> str:
            return json.dumps(
                service.summarise_issue_history(issue_id, user=user),
                default=str,
            )

        def create_next_action(issue_id: int) -> str:
            return json.dumps(
                service.create_next_action(issue_id, user=user),
                default=str,
            )

        return [
            StructuredTool.from_function(
                func=get_customer_profile,
                name="get_customer_profile",
                description="Retrieve the customer profile using the customer name",
                args_schema=CustomerNameArgs,
            ),
            StructuredTool.from_function(
                func=get_open_issues_for_customer,
                name="get_open_issues_for_customer",
                description="Retrieve all open issues for a given customer",
                args_schema=CustomerNameArgs,
            ),
            StructuredTool.from_function(
                func=summarise_issue_history,
                name="summarise_issue_history",
                description=(
                    "Summarise the history of a specific issue using an LLM grounded "
                    "in the issue updates and next actions"
                ),
                args_schema=IssueIdArgs,
            ),
            StructuredTool.from_function(
                func=create_next_action,
                name="create_next_action",
                description=(
                    "Generate an LLM recommendation for the next action on an issue "
                    "and persist it. Only support_user or admin may succeed."
                ),
                args_schema=IssueIdArgs,
            ),
        ]

    def _extract_reply(self, messages: list[Any]) -> str:
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content:
                content = message.content
                if isinstance(content, str) and content.strip():
                    return content.strip()
                if isinstance(content, list):
                    texts = [
                        block.get("text", "")
                        for block in content
                        if isinstance(block, dict) and block.get("type") == "text"
                    ]
                    joined = "\n".join(t for t in texts if t).strip()
                    if joined:
                        return joined
        return "I could not produce a reply."

    def _extract_tool_trace(self, messages: list[Any]) -> list[dict[str, Any]]:
        trace: list[dict[str, Any]] = []
        pending: dict[str, dict[str, Any]] = {}

        for message in messages:
            if isinstance(message, AIMessage) and message.tool_calls:
                for call in message.tool_calls:
                    call_id = call.get("id") or ""
                    entry = {
                        "tool": call.get("name"),
                        "args": call.get("args") or {},
                        "id": call_id,
                    }
                    pending[call_id] = entry
                    trace.append(entry)
            elif isinstance(message, ToolMessage):
                call_id = getattr(message, "tool_call_id", "") or ""
                entry = pending.get(call_id)
                if entry is not None:
                    entry["result"] = message.content
                else:
                    trace.append(
                        {
                            "tool": getattr(message, "name", None),
                            "result": message.content,
                        }
                    )
        return trace
