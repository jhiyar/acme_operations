from __future__ import annotations

import json
from typing import Any

from core.services.agent_tool_service import AgentToolService
from core.services.keycloak_auth_service import KeycloakUser
from core.services.llm import get_llm_client
from core.services.llm.base import LlmClient, LlmMessage

ESCALATION_SYSTEM = """You are an operations risk analyst.
Given a customer profile, open issues, and optional issue summaries, produce a Customer Escalation Summary.
Return STRICT JSON with keys:
- executive_summary (string)
- risk_level (one of: Low, Medium, High, Critical)
- recommended_next_action (string)
- missing_information (array of strings)
- rationale (string)
Do not invent facts not present in the input. If data is thin, say so in missing_information.
"""


class CustomerEscalationSummarySkill:
    """
    Reusable multi-step Skill (not a one-off prompt).

    Workflow:
    1) Load customer profile
    2) Load open issues
    3) Summarise up to N highest-priority open issues
    4) Ask the LLM for a structured escalation brief
    """

    name = "customer_escalation_summary"
    description = (
        "Run the Customer Escalation Summary skill for a customer: gather profile, "
        "open issues, issue summaries, then produce executive summary, risk level, "
        "recommended next action, and missing information."
    )

    def __init__(
        self,
        tools: AgentToolService | None = None,
        llm: LlmClient | None = None,
        max_issue_summaries: int = 3,
    ) -> None:
        self.tools = tools or AgentToolService()
        self._llm = llm
        self.max_issue_summaries = max_issue_summaries

    @property
    def llm(self) -> LlmClient:
        if self._llm is None:
            self._llm = get_llm_client()
        return self._llm

    def run(self, customer_name: str, user: KeycloakUser) -> dict[str, Any]:
        profile = self.tools.get_customer_profile(customer_name, user=user)
        if not profile.get("found"):
            return {
                "skill": self.name,
                "completed": False,
                "error": f"Customer not found: {customer_name}",
                "profile": profile,
            }

        open_issues = self.tools.get_open_issues_for_customer(customer_name, user=user)
        issues = list(open_issues.get("issues") or [])
        priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        issues.sort(key=lambda i: priority_rank.get(str(i.get("priority", "")).lower(), 9))

        issue_summaries: list[dict[str, Any]] = []
        for issue in issues[: self.max_issue_summaries]:
            issue_id = int(issue["id"])
            summary = self.tools.summarise_issue_history(issue_id, user=user)
            issue_summaries.append(
                {
                    "issue_id": issue_id,
                    "title": issue.get("title"),
                    "priority": issue.get("priority"),
                    "status": issue.get("status"),
                    "summary": summary.get("summary"),
                }
            )

        payload = {
            "customer": profile.get("customer"),
            "open_issue_count": open_issues.get("open_issue_count", len(issues)),
            "open_issues": issues,
            "issue_summaries": issue_summaries,
        }
        llm_response = self.llm.complete(
            [LlmMessage(role="user", content=json.dumps(payload, default=str))],
            system=ESCALATION_SYSTEM,
            purpose="customer_escalation_summary",
        )
        structured = self._parse_json(llm_response.text)

        return {
            "skill": self.name,
            "completed": True,
            "customer_name": profile["customer"]["name"],
            "inputs": {
                "profile_found": True,
                "open_issue_count": payload["open_issue_count"],
                "summarised_issue_ids": [s["issue_id"] for s in issue_summaries],
            },
            "result": structured,
            "raw_model_text": llm_response.text,
        }

    def _parse_json(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return {
            "executive_summary": text.strip(),
            "risk_level": "Medium",
            "recommended_next_action": "",
            "missing_information": ["Model did not return valid JSON"],
            "rationale": "",
        }
