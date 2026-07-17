from __future__ import annotations

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission

from core.permissions import ASSISTANT_ROLES, can_use_assistant
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


class IsAuthenticatedKeycloak(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and getattr(user, "is_authenticated", False))


class HasRealmRole(BasePermission):
    """Subclass and set `allowed_roles`."""

    allowed_roles = ()

    def has_permission(self, request, view):
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        user_roles = set(getattr(user, "roles", []))
        return bool(user_roles.intersection(self.allowed_roles))


class CanUseAssistant(BasePermission):
    def has_permission(self, request, view):
        return can_use_assistant(request.user)


def keycloak_settings():
    return {
        "server_url": settings.KEYCLOAK_SERVER_URL.rstrip("/"),
        "realm": settings.KEYCLOAK_REALM,
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "audience": getattr(settings, "KEYCLOAK_AUDIENCE", settings.KEYCLOAK_CLIENT_ID),
        "assistant_roles": ASSISTANT_ROLES,
    }
