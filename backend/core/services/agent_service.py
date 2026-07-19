from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from django.conf import settings
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from core.services.agent_tool_service import AgentToolService
from core.services.conversation_service import ConversationService
from core.services.keycloak_auth_service import KeycloakUser
from core.services.llm import get_chat_model
from core.services.llm_logging import record_llm_call, usage_from_ai_message
from core.services.memory_service import MemoryService
from core.skills import CustomerEscalationSummarySkill

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """You are Acme Operations assistant.
Use tools to look up customers and issues. Never invent customer names, issue IDs, or facts.
If the user asks multiple things, call as many tools as needed and answer every part in your final reply.
For recommended next actions, call create_next_action (it generates and persists the recommendation).
For executive escalation briefs (risk, summary, missing info), call customer_escalation_summary.
If a tool returns an error (including RBAC), explain it clearly to the user.

Customer names may be partial (e.g. "Contoso" for "Contoso Ltd") — still call the tools.
If the user mentions a nickname or symptom (e.g. "Client X warehouse", "tracking is broken")
rather than a formal customer name, call get_open_issues_for_customer with that phrase so the
tool can keyword-match open issues. Do not assume the nickname is a customer record.
When a tool returns candidates or keyword matches, use those results instead of asking the user
to guess names.
"""


class CustomerNameArgs(BaseModel):
    customer_name: str = Field(description="Exact or case-insensitive customer name")


class IssueIdArgs(BaseModel):
    issue_id: int = Field(description="Issue primary key")


@dataclass
class AgentReply:
    reply: str
    tool_trace: list[dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    llm_call_count: int = 0


def _is_uuid(value: str | None) -> bool:
    if not value:
        return False
    try:
        UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _truncate_turn(content: str, limit: int) -> str:
    text = (content or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


class AgentService:
    """LangGraph ReAct agent that selects and invokes tools dynamically."""

    def __init__(
        self,
        tools: AgentToolService | None = None,
        chat_model: Any | None = None,
        memory: MemoryService | None = None,
        skill: CustomerEscalationSummarySkill | None = None,
        conversations: ConversationService | None = None,
    ) -> None:
        self.tools = tools or AgentToolService()
        self._chat_model = chat_model
        self.memory = memory or MemoryService()
        self.skill = skill or CustomerEscalationSummarySkill(tools=self.tools)
        self.conversations = conversations or ConversationService()

    @property
    def chat_model(self) -> Any:
        if self._chat_model is None:
            self._chat_model = get_chat_model()
        return self._chat_model

    def run(
        self,
        message: str,
        user: KeycloakUser,
        *,
        session_id: str | None = None,
    ) -> AgentReply:
        structured_tools = self._build_tools(user)
        history = self._load_history(user.sub, session_id=session_id)
        messages: list[Any] = []
        for turn in history:
            role = turn.get("role")
            content = turn.get("content") or ""
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        messages.append(HumanMessage(content=message))

        agent = create_react_agent(
            self.chat_model,
            structured_tools,
            prompt=AGENT_SYSTEM_PROMPT,
        )
        result = agent.invoke(
            {"messages": messages},
            config={"recursion_limit": settings.AGENT_MAX_TOOL_ROUNDS * 2},
        )
        result_messages = result.get("messages") or []
        reply = self._extract_reply(result_messages)
        tool_trace = self._extract_tool_trace(result_messages)
        usage = self._record_agent_llm_usage(result_messages)

        # Keep Redis warm for low-latency follow-ups / eval harness.
        self.memory.append_turn(user.sub, "user", message, session_id=session_id)
        self.memory.append_turn(
            user.sub,
            "assistant",
            reply,
            session_id=session_id,
            tool_trace=tool_trace,
        )
        return AgentReply(
            reply=reply,
            tool_trace=tool_trace,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            llm_call_count=usage["llm_call_count"],
        )

    def _load_history(
        self,
        user_sub: str,
        *,
        session_id: str | None,
    ) -> list[dict[str, str]]:
        """
        Sliding-window history for the model.

        Chat conversations (UUID session_id) use Postgres as source of truth so
        Redis TTL / outages do not wipe multi-turn context. Redis is still used
        for non-conversation sessions (e.g. eval) and as a warm cache write.
        """
        limit = max(1, int(getattr(settings, "AGENT_HISTORY_MAX_TURNS", 8)))
        max_chars = max(
            1,
            int(getattr(settings, "AGENT_HISTORY_MAX_CHARS_PER_TURN", 1200)),
        )
        turns: list[dict[str, str]] = []

        if _is_uuid(session_id):
            try:
                turns = self.conversations.recent_turns_for_agent(
                    session_id,  # type: ignore[arg-type]
                    limit=limit,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Postgres history unavailable: %s", exc)
                turns = []

        if not turns:
            turns = [
                {"role": str(t.get("role") or ""), "content": str(t.get("content") or "")}
                for t in self.memory.get_history(user_sub, session_id=session_id, limit=limit)
            ]

        trimmed = [
            {
                "role": turn["role"],
                "content": _truncate_turn(turn.get("content") or "", max_chars),
            }
            for turn in turns
            if turn.get("role") in {"user", "assistant"} and (turn.get("content") or "").strip()
        ]

        # Rehydrate Redis from durable history so a cold cache warms quickly.
        if _is_uuid(session_id) and trimmed and self.memory.enabled:
            existing = self.memory.get_history(user_sub, session_id=session_id, limit=limit)
            if not existing:
                for turn in trimmed:
                    self.memory.append_turn(
                        user_sub,
                        turn["role"],
                        turn["content"],
                        session_id=session_id,
                    )

        return trimmed

    def _build_tools(self, user: KeycloakUser) -> list[StructuredTool]:
        service = self.tools
        skill = self.skill

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

        def customer_escalation_summary(customer_name: str) -> str:
            return json.dumps(skill.run(customer_name, user), default=str)

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
                description=(
                    "Retrieve open issues for a customer name, or keyword-match open "
                    "issues when the phrase is not an exact customer "
                    "(e.g. Client X, warehouse tracking)"
                ),
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
            StructuredTool.from_function(
                func=customer_escalation_summary,
                name="customer_escalation_summary",
                description=CustomerEscalationSummarySkill.description,
                args_schema=CustomerNameArgs,
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

    def _record_agent_llm_usage(self, messages: list[Any]) -> dict[str, int]:
        provider = (settings.LLM_PROVIDER or "").strip().lower()
        model = (
            settings.ANTHROPIC_MODEL
            if provider == "anthropic"
            else settings.OPENAI_MODEL
        )
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        llm_call_count = 0

        for message in messages:
            if not isinstance(message, AIMessage):
                continue
            prompt, completion, total = usage_from_ai_message(message)
            if prompt == 0 and completion == 0 and total == 0:
                # Still count an agent model step when usage metadata is missing.
                if message.content or message.tool_calls:
                    llm_call_count += 1
                    record_llm_call(
                        provider=provider or "unknown",
                        model=model,
                        purpose="agent",
                    )
                continue
            prompt_tokens += prompt
            completion_tokens += completion
            total_tokens += total
            llm_call_count += 1
            record_llm_call(
                provider=provider or "unknown",
                model=model,
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=total,
                purpose="agent",
                request_id=str(
                    (getattr(message, "response_metadata", None) or {}).get("id") or ""
                ),
            )

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "llm_call_count": llm_call_count,
        }
