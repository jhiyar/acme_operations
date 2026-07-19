"""
Acme custom MCP server.

Exposes the same domain tools as the LangGraph agent, but as an MCP server so
external clients (Cursor, Claude Desktop, other agents) can call them without
embedding Acme business logic.

Local demo caveat: tools run as a synthetic Keycloak admin user so MCP callers
do not need to pass end-user JWTs. Do not treat this as a production auth model.

Run (Docker / Python 3.10+):
  python -m mcp_server
"""

from __future__ import annotations

import json
import os
import sys


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

    @mcp.tool()
    def get_customer_profile(customer_name: str) -> str:
        """Retrieve the customer profile using the customer name."""
        return json.dumps(
            tools.get_customer_profile(customer_name, user=_svc_user()),
            default=str,
        )

    @mcp.tool()
    def get_open_issues_for_customer(customer_name: str) -> str:
        """Retrieve open issues for a customer (supports keyword match)."""
        return json.dumps(
            tools.get_open_issues_for_customer(customer_name, user=_svc_user()),
            default=str,
        )

    @mcp.tool()
    def summarise_issue_history(issue_id: int) -> str:
        """Summarise the history of a specific issue."""
        return json.dumps(
            tools.summarise_issue_history(issue_id, user=_svc_user()),
            default=str,
        )

    @mcp.tool()
    def create_next_action(issue_id: int) -> str:
        """Generate and persist a recommended next action for an issue."""
        return json.dumps(
            tools.create_next_action(issue_id, user=_svc_user()),
            default=str,
        )

    @mcp.tool()
    def customer_escalation_summary(customer_name: str) -> str:
        """Run the Customer Escalation Summary skill for a customer."""
        return json.dumps(skill.run(customer_name, _svc_user()), default=str)

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
