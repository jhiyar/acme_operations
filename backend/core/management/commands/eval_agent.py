from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from core.services.agent_service import AgentService
from core.services.agent_tool_service import AgentToolService
from core.services.keycloak_auth_service import KeycloakUser
from core.services.llm import get_chat_model, get_llm_client
from issues.models import Issue


@dataclass
class EvalCase:
    id: str
    question: str
    username: str
    roles: list[str]
    expect_tools: list[str] = field(default_factory=list)
    expect_any_tools: list[str] = field(default_factory=list)
    forbid_tools: list[str] = field(default_factory=list)
    expect_reply_contains: list[str] = field(default_factory=list)
    expect_reply_regex: list[str] = field(default_factory=list)
    session_id: str | None = None
    prior_turns: list[dict[str, str]] = field(default_factory=list)
    follow_up: str | None = None
    follow_up_expect_reply_contains: list[str] = field(default_factory=list)
    follow_up_forbid_tools: list[str] = field(default_factory=list)
    expect_memory_min_turns: int = 0
    expect_customer_cached: str | None = None
    notes: str = ""


def _user(username: str, roles: list[str]) -> KeycloakUser:
    return KeycloakUser(
        sub=f"eval-{username}",
        username=username,
        email=f"{username}@example.com",
        roles=roles,
    )


def build_cases() -> list[EvalCase]:
    contoso_critical = (
        Issue.objects.filter(
            customer__name__iexact="Contoso Ltd",
            title__icontains="alert noise",
        )
        .order_by("id")
        .first()
    )
    northwind_tracking = (
        Issue.objects.filter(
            customer__name__iexact="Northwind Traders",
            title__icontains="shipment tracking",
        )
        .order_by("id")
        .first()
    )
    fabrikam_sso = (
        Issue.objects.filter(
            customer__name__iexact="Fabrikam Inc",
            title__icontains="SSO",
        )
        .order_by("id")
        .first()
    )

    c_id = contoso_critical.id if contoso_critical else 0
    n_id = northwind_tracking.id if northwind_tracking else 0
    f_id = fabrikam_sso.id if fabrikam_sso else 0

    return [
        EvalCase(
            id="Q01_contoso_profile",
            question="What is the customer profile for Contoso Ltd?",
            username="support",
            roles=["support_user"],
            expect_tools=["get_customer_profile"],
            expect_reply_contains=["Contoso"],
            notes="Single-tool customer lookup",
        ),
        EvalCase(
            id="Q02_northwind_open_issues",
            question="List all open issues for Northwind Traders.",
            username="admin",
            roles=["admin"],
            expect_tools=["get_open_issues_for_customer"],
            expect_reply_contains=["Northwind"],
            notes="Open issues listing",
        ),
        EvalCase(
            id="Q03_summarise_contoso_critical",
            question=(
                f"Summarise the history of Contoso issue #{c_id} "
                "(production line alert noise)."
            ),
            username="support",
            roles=["support_user"],
            expect_tools=["summarise_issue_history"],
            expect_reply_contains=["alert"],
            notes="LLM summary tool",
        ),
        EvalCase(
            id="Q04_create_next_action_support",
            question=(
                f"Create a recommended next action for Contoso issue #{c_id}."
            ),
            username="support",
            roles=["support_user"],
            expect_tools=["create_next_action"],
            notes="Support can create next actions",
        ),
        EvalCase(
            id="Q05_create_next_action_sales_rbac",
            question=(
                f"Please create a next action recommendation for issue #{n_id}."
            ),
            username="sales",
            roles=["sales_user"],
            expect_tools=["create_next_action"],
            expect_reply_contains=["support"],
            notes="Sales should be denied by RBAC and agent should explain",
        ),
        EvalCase(
            id="Q06_compound_contoso",
            question=(
                f"For Contoso: give me the customer profile, list open issues, "
                f"summarise issue #{c_id}, and create a next action for it."
            ),
            username="support",
            roles=["support_user"],
            expect_tools=[
                "get_customer_profile",
                "get_open_issues_for_customer",
                "summarise_issue_history",
                "create_next_action",
            ],
            notes="Compound multi-tool question",
        ),
        EvalCase(
            id="Q07_unknown_customer",
            question="Show me the profile for Globex Corporation.",
            username="admin",
            roles=["admin"],
            expect_tools=["get_customer_profile"],
            expect_reply_regex=[r"(?i)(not found|no customer|couldn't find|could not find|unknown|doesn't exist|does not exist)"],
            notes="Missing customer should not be invented",
        ),
        EvalCase(
            id="Q08_fabrikam_sso_summary",
            question=(
                f"What is going on with Fabrikam issue #{f_id} about SSO mapping? "
                "Summarise it."
            ),
            username="admin",
            roles=["admin"],
            expect_tools=["summarise_issue_history"],
            expect_reply_contains=["SSO"],
            notes="Fabrikam SSO grounding",
        ),
        EvalCase(
            id="Q09_northwind_invoice_and_profile",
            question=(
                "Tell me about Northwind Traders as a customer and whether they have "
                "any open billing/invoice related issues."
            ),
            username="sales",
            roles=["sales_user"],
            expect_any_tools=[
                "get_customer_profile",
                "get_open_issues_for_customer",
            ],
            expect_reply_contains=["Northwind"],
            notes="Profile + open issues without hardcoded routing",
        ),
        EvalCase(
            id="Q10_no_tools_chitchat",
            question="Thanks — what can you help me with in one short sentence?",
            username="admin",
            roles=["admin"],
            forbid_tools=[
                "create_next_action",
            ],
            notes="Chitchat should not force tool use / writes",
        ),
        EvalCase(
            id="Q11_ambiguous_client_x",
            question=(
                "Client X warehouse tracking is broken — which customer/issue is that, "
                "and what should we do next?"
            ),
            username="admin",
            roles=["admin"],
            expect_any_tools=[
                "get_open_issues_for_customer",
                "summarise_issue_history",
                "get_customer_profile",
                "create_next_action",
            ],
            expect_reply_contains=["Northwind"],
            notes="Ambiguous Client X should resolve to Northwind tracking issue (admin visibility)",
        ),
        EvalCase(
            id="Q12_open_issues_contoso_only",
            question="Which Contoso issues are still open?",
            username="support",
            roles=["support_user"],
            expect_tools=["get_open_issues_for_customer"],
            expect_reply_contains=["alert"],
            notes="Should not include resolved Contoso access request as open",
        ),
        EvalCase(
            id="Q13_escalation_skill",
            question=(
                "Run a customer escalation summary for Contoso Ltd — I need risk level "
                "and recommended next action for the account."
            ),
            username="support",
            roles=["support_user"],
            expect_tools=["customer_escalation_summary"],
            expect_reply_regex=[r"(?i)(risk|critical|high|medium|low)"],
            notes="Reusable Customer Escalation Summary skill",
        ),
        EvalCase(
            id="Q14_redis_session_memory",
            question=(
                "My focus account for this session is Contoso Ltd. "
                "Acknowledge that in one short sentence; do not look anything up yet."
            ),
            username="support",
            roles=["support_user"],
            session_id="eval-memory-q14",
            follow_up=(
                "Without looking anything up, which customer did I say is my focus "
                "account for this session?"
            ),
            follow_up_expect_reply_contains=["Contoso"],
            follow_up_forbid_tools=[
                "get_customer_profile",
                "get_open_issues_for_customer",
                "summarise_issue_history",
                "create_next_action",
                "customer_escalation_summary",
            ],
            expect_memory_min_turns=4,
            notes="Redis session memory should carry Contoso across turns",
        ),
        EvalCase(
            id="Q15_redis_customer_cache",
            question="What is the customer profile for Contoso Ltd?",
            username="support",
            roles=["support_user"],
            session_id="eval-cache-q15",
            expect_tools=["get_customer_profile"],
            expect_reply_contains=["Contoso"],
            expect_customer_cached="Contoso Ltd",
            expect_memory_min_turns=2,
            notes="Profile lookup should populate Redis customer cache + session turns",
        ),
    ]


def score_case(
    case: EvalCase,
    *,
    tools_used: list[str],
    reply: str,
    error: str | None,
    follow_up_tools_used: list[str] | None = None,
    follow_up_reply: str | None = None,
    memory_turn_count: int = 0,
    customer_cached: bool | None = None,
    redis_enabled: bool | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    passed = True

    if error:
        checks.append({"name": "no_error", "pass": False, "detail": error})
        return {"pass": False, "checks": checks}

    checks.append({"name": "no_error", "pass": True})

    for tool in case.expect_tools:
        ok = tool in tools_used
        checks.append({"name": f"expect_tool:{tool}", "pass": ok})
        passed = passed and ok

    if case.expect_any_tools:
        ok = any(t in tools_used for t in case.expect_any_tools)
        checks.append(
            {
                "name": "expect_any_tools",
                "pass": ok,
                "detail": case.expect_any_tools,
            }
        )
        passed = passed and ok

    for tool in case.forbid_tools:
        ok = tool not in tools_used
        checks.append({"name": f"forbid_tool:{tool}", "pass": ok})
        passed = passed and ok

    reply_l = reply or ""
    for needle in case.expect_reply_contains:
        ok = needle.lower() in reply_l.lower()
        checks.append({"name": f"reply_contains:{needle}", "pass": ok})
        passed = passed and ok

    for pattern in case.expect_reply_regex:
        ok = bool(re.search(pattern, reply_l))
        checks.append({"name": f"reply_regex:{pattern}", "pass": ok})
        passed = passed and ok

    if not reply_l.strip():
        checks.append({"name": "non_empty_reply", "pass": False})
        passed = False
    else:
        checks.append({"name": "non_empty_reply", "pass": True})

    if case.follow_up:
        fu_reply = follow_up_reply or ""
        fu_tools = follow_up_tools_used or []
        for needle in case.follow_up_expect_reply_contains:
            ok = needle.lower() in fu_reply.lower()
            checks.append({"name": f"follow_up_reply_contains:{needle}", "pass": ok})
            passed = passed and ok
        for tool in case.follow_up_forbid_tools:
            ok = tool not in fu_tools
            checks.append({"name": f"follow_up_forbid_tool:{tool}", "pass": ok})
            passed = passed and ok
        if not fu_reply.strip():
            checks.append({"name": "follow_up_non_empty_reply", "pass": False})
            passed = False
        else:
            checks.append({"name": "follow_up_non_empty_reply", "pass": True})

    if case.expect_memory_min_turns or case.expect_customer_cached:
        if redis_enabled is False:
            checks.append(
                {
                    "name": "redis_enabled",
                    "pass": False,
                    "detail": "Redis unavailable; cannot validate memory/cache",
                }
            )
            passed = False
        else:
            checks.append({"name": "redis_enabled", "pass": True})

    if case.expect_memory_min_turns:
        ok = memory_turn_count >= case.expect_memory_min_turns
        checks.append(
            {
                "name": f"memory_min_turns:{case.expect_memory_min_turns}",
                "pass": ok,
                "detail": memory_turn_count,
            }
        )
        passed = passed and ok

    if case.expect_customer_cached:
        ok = bool(customer_cached)
        checks.append(
            {
                "name": f"customer_cached:{case.expect_customer_cached}",
                "pass": ok,
            }
        )
        passed = passed and ok

    return {"pass": passed, "checks": checks}


class Command(BaseCommand):
    help = (
        "Run offline agent evaluation questions, score tool use / replies, "
        "and write results under backend/evals/results/."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--provider",
            default=None,
            help="Override LLM_PROVIDER for this run (anthropic|openai)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Run only the first N cases (0 = all)",
        )
        parser.add_argument(
            "--case",
            action="append",
            default=[],
            help="Run only these case ids (repeatable)",
        )

    def handle(self, *args, **options) -> None:
        provider = (options["provider"] or settings.LLM_PROVIDER).strip().lower()
        cases = build_cases()
        if options["case"]:
            wanted = set(options["case"])
            cases = [c for c in cases if c.id in wanted]
        if options["limit"] and options["limit"] > 0:
            cases = cases[: options["limit"]]

        out_dir = Path(settings.BASE_DIR) / "evals" / "results"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        json_path = out_dir / f"eval_{provider}_{stamp}.json"
        md_path = out_dir / f"eval_{provider}_{stamp}.md"
        latest_json = out_dir / "latest.json"
        latest_md = out_dir / "latest.md"

        self.stdout.write(
            self.style.NOTICE(
                f"Running {len(cases)} cases with provider={provider} "
                f"(model anthropic={settings.ANTHROPIC_MODEL}, openai={settings.OPENAI_MODEL})"
            )
        )

        from core.services.llm import get_chat_model, get_llm_client
        from core.services.memory_service import MemoryService

        memory = MemoryService()
        agent = AgentService(
            chat_model=get_chat_model(provider),
            tools=AgentToolService(llm=get_llm_client(provider), memory=memory),
            memory=memory,
        )

        results: list[dict[str, Any]] = []
        passed_count = 0

        for index, case in enumerate(cases, start=1):
            self.stdout.write(f"[{index}/{len(cases)}] {case.id} …")
            started = time.perf_counter()
            error: str | None = None
            reply = ""
            tool_trace: list[dict[str, Any]] = []
            follow_up_reply = ""
            follow_up_tool_trace: list[dict[str, Any]] = []
            user = _user(case.username, case.roles)
            session_id = case.session_id or f"eval-{case.id}"

            try:
                for turn in case.prior_turns:
                    memory.append_turn(
                        user.sub,
                        turn["role"],
                        turn["content"],
                        session_id=session_id,
                    )

                outcome = agent.run(
                    case.question,
                    user,
                    session_id=session_id,
                )
                reply = outcome.reply
                tool_trace = outcome.tool_trace

                if case.follow_up:
                    follow_up = agent.run(
                        case.follow_up,
                        user,
                        session_id=session_id,
                    )
                    follow_up_reply = follow_up.reply
                    follow_up_tool_trace = follow_up.tool_trace
            except Exception as exc:  # noqa: BLE001
                error = str(exc)

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            tools_used = [
                str(step.get("tool"))
                for step in tool_trace
                if step.get("tool")
            ]
            follow_up_tools_used = [
                str(step.get("tool"))
                for step in follow_up_tool_trace
                if step.get("tool")
            ]
            history = memory.get_history(user.sub, session_id=session_id)
            cached = (
                memory.get_cached_customer(case.expect_customer_cached)
                if case.expect_customer_cached
                else None
            )
            scoring = score_case(
                case,
                tools_used=tools_used,
                reply=reply,
                error=error,
                follow_up_tools_used=follow_up_tools_used,
                follow_up_reply=follow_up_reply,
                memory_turn_count=len(history),
                customer_cached=cached is not None,
                redis_enabled=memory.enabled,
            )
            if scoring["pass"]:
                passed_count += 1
                self.stdout.write(self.style.SUCCESS(f"  PASS ({elapsed_ms}ms) tools={tools_used}"))
            else:
                self.stdout.write(self.style.ERROR(f"  FAIL ({elapsed_ms}ms) tools={tools_used}"))
                if error:
                    self.stdout.write(self.style.ERROR(f"  error: {error}"))
                failed = [c["name"] for c in scoring["checks"] if not c["pass"]]
                if failed:
                    self.stdout.write(self.style.ERROR(f"  failed: {failed}"))

            results.append(
                {
                    "id": case.id,
                    "question": case.question,
                    "follow_up": case.follow_up,
                    "username": case.username,
                    "roles": case.roles,
                    "notes": case.notes,
                    "session_id": session_id,
                    "expect_tools": case.expect_tools,
                    "expect_any_tools": case.expect_any_tools,
                    "forbid_tools": case.forbid_tools,
                    "elapsed_ms": elapsed_ms,
                    "error": error,
                    "tools_used": tools_used,
                    "tool_trace": tool_trace,
                    "reply": reply,
                    "follow_up_tools_used": follow_up_tools_used,
                    "follow_up_reply": follow_up_reply,
                    "memory_turn_count": len(history),
                    "customer_cached": bool(cached),
                    "redis_enabled": memory.enabled,
                    "scoring": scoring,
                }
            )

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "anthropic_model": settings.ANTHROPIC_MODEL,
            "openai_model": settings.OPENAI_MODEL,
            "total": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "results": results,
        }

        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        latest_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        md = self._to_markdown(payload)
        md_path.write_text(md, encoding="utf-8")
        latest_md.write_text(md, encoding="utf-8")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Score: {passed_count}/{len(results)}  →  {json_path}"
            )
        )

    def _to_markdown(self, payload: dict[str, Any]) -> str:
        lines = [
            f"# Agent eval ({payload['provider']})",
            "",
            f"- Generated: `{payload['generated_at']}`",
            f"- Score: **{payload['passed']}/{payload['total']}**",
            f"- Anthropic model: `{payload['anthropic_model']}`",
            f"- OpenAI model: `{payload['openai_model']}`",
            "",
        ]
        for row in payload["results"]:
            status = "PASS" if row["scoring"]["pass"] else "FAIL"
            lines.extend(
                [
                    f"## {row['id']} — {status}",
                    "",
                    f"**Q:** {row['question']}",
                    "",
                    f"- User: `{row['username']}` roles={row['roles']}",
                    f"- Tools used: `{row['tools_used']}`",
                    f"- Elapsed: {row['elapsed_ms']} ms",
                ]
            )
            if row.get("follow_up"):
                lines.extend(
                    [
                        "",
                        f"**Follow-up:** {row['follow_up']}",
                        f"- Follow-up tools: `{row.get('follow_up_tools_used')}`",
                        f"- Memory turns: `{row.get('memory_turn_count')}`",
                        f"- Redis enabled: `{row.get('redis_enabled')}`",
                    ]
                )
            if row.get("error"):
                lines.append(f"- Error: `{row['error']}`")
            failed = [c for c in row["scoring"]["checks"] if not c["pass"]]
            if failed:
                lines.append("- Failed checks:")
                for check in failed:
                    lines.append(f"  - `{check['name']}`")
            lines.extend(["", "### Reply", "", row.get("reply") or "_(empty)_", ""])
            if row.get("follow_up"):
                lines.extend(
                    [
                        "### Follow-up reply",
                        "",
                        row.get("follow_up_reply") or "_(empty)_",
                        "",
                    ]
                )
        return "\n".join(lines)
