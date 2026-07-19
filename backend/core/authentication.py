from __future__ import annotations

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from core.services.keycloak_auth_service import KeycloakAuthService


class KeycloakJWTAuthentication(BaseAuthentication):
    """Authenticate requests with a Keycloak bearer JWT."""

    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith("Bearer "):
            return None

        token = header[len("Bearer ") :].strip()
        if not token:
            return None

        try:
            user = KeycloakAuthService().verify_token(token)
        except Exception as exc:
            raise AuthenticationFailed(str(exc)) from exc

        return (user, token)
