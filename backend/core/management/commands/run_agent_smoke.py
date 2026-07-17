from django.core.management.base import BaseCommand, CommandError

from core.services.agent_service import AgentService
from core.services.keycloak_auth_service import KeycloakUser


class Command(BaseCommand):
    help = (
        "Manually run the LangGraph agent against a real LLM. "
        "Requires ANTHROPIC_API_KEY (or OPENAI_API_KEY when LLM_PROVIDER=openai). "
        "Not part of automated tests."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--message",
            required=True,
            help="User message to send to the agent",
        )
        parser.add_argument(
            "--username",
            default="admin",
            help="Synthetic username for RBAC (default: admin)",
        )
        parser.add_argument(
            "--role",
            default="admin",
            help="Synthetic role for RBAC (default: admin)",
        )

    def handle(self, *args, **options) -> None:
        user = KeycloakUser(
            sub="smoke-test",
            username=options["username"],
            email=f"{options['username']}@example.com",
            roles=[options["role"]],
        )
        try:
            result = AgentService().run(options["message"], user)
        except Exception as exc:  # noqa: BLE001 — surface config/network errors to CLI
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS("=== reply ==="))
        self.stdout.write(result.reply)
        self.stdout.write(self.style.SUCCESS("=== tool_trace ==="))
        for step in result.tool_trace:
            self.stdout.write(str(step))
