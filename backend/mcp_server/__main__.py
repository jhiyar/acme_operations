"""
Acme custom MCP server.

Exposes the same domain tools as the LangGraph agent, but as an MCP server so
external clients (Cursor, Claude Desktop, other agents) can call them without
embedding Acme business logic.

Local demo caveat: tools run as a synthetic Keycloak admin user so MCP callers
do not need to pass end-user JWTs. Do not treat this as a production auth model.

FastMCP runs tools in an async event loop; Django ORM is sync-only, so each
tool body is awaited via sync_to_async.

Run (Docker / Python 3.10+):
  python -m mcp_server
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Callable


def _bootstrap_django() -> None:
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_root not in sys.path:
        sys.path.insert(0, backend_root)
    django.setup()


def main() -> None:
    _bootstrap_django()

    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "The 'mcp' package requires Python >= 3.10. "
            "Run this server inside the Docker mcp service."
        ) from exc

    from asgiref.sync import sync_to_async

    from core.services.agent_tool_service import AgentToolService
    from core.services.keycloak_auth_service import KeycloakUser
    from core.skills import CustomerEscalationSummarySkill

    mcp = FastMCP("acme-operations")
    tools = AgentToolService()
    skill = CustomerEscalationSummarySkill(tools=tools)

    def _svc_user() -> KeycloakUser:
        return KeycloakUser(
            sub="mcp-service",
            username="mcp",
            email="mcp@acme.local",
            roles=["admin"],
        )

    async def _call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        result = await sync_to_async(fn, thread_sensitive=True)(*args, **kwargs)
        return json.dumps(result, default=str)

    @mcp.tool()
    async def get_customer_profile(customer_name: str) -> str:
        """Retrieve the customer profile using the customer name."""
        return await _call(
            tools.get_customer_profile,
            customer_name,
            user=_svc_user(),
        )

    @mcp.tool()
    async def get_open_issues_for_customer(customer_name: str) -> str:
        """Retrieve open issues for a customer (supports keyword match)."""
        return await _call(
            tools.get_open_issues_for_customer,
            customer_name,
            user=_svc_user(),
        )

    @mcp.tool()
    async def summarise_issue_history(issue_id: int) -> str:
        """Summarise the history of a specific issue."""
        return await _call(
            tools.summarise_issue_history,
            issue_id,
            user=_svc_user(),
        )

    @mcp.tool()
    async def create_next_action(issue_id: int) -> str:
        """Generate and persist a recommended next action for an issue."""
        return await _call(
            tools.create_next_action,
            issue_id,
            user=_svc_user(),
        )

    @mcp.tool()
    async def customer_escalation_summary(customer_name: str) -> str:
        """Run the Customer Escalation Summary skill for a customer."""
        return await _call(skill.run, customer_name, _svc_user())

    transport = os.environ.get("MCP_TRANSPORT", "sse")
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    port = int(os.environ.get("MCP_PORT", "8001"))

    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.run(transport="sse")


if __name__ == "__main__":
    main()
