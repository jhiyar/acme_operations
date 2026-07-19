from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from rest_framework.permissions import BasePermission

if TYPE_CHECKING:
    from core.services.keycloak_auth_service import KeycloakUser

ROLE_ADMIN = "admin"
ROLE_SALES = "sales_user"
ROLE_SUPPORT = "support_user"

ASSISTANT_ROLES = (ROLE_SALES, ROLE_SUPPORT, ROLE_ADMIN)


def _roles(user: KeycloakUser | None) -> set[str]:
    if not user:
        return set()
    return set(getattr(user, "roles", []) or [])


def has_role(user: KeycloakUser | None, role: str) -> bool:
    return role in _roles(user)


def has_any_role(user: KeycloakUser | None, roles: Iterable[str]) -> bool:
    return bool(_roles(user).intersection(roles))


def is_admin(user: KeycloakUser | None) -> bool:
    return has_role(user, ROLE_ADMIN)


def is_sales(user: KeycloakUser | None) -> bool:
    return has_role(user, ROLE_SALES)


def is_support(user: KeycloakUser | None) -> bool:
    return has_role(user, ROLE_SUPPORT)


def can_use_assistant(user: KeycloakUser | None) -> bool:
    return has_any_role(user, ASSISTANT_ROLES)


class IsAuthenticatedKeycloak(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and getattr(user, "is_authenticated", False))


class CanUseAssistant(BasePermission):
    def has_permission(self, request, view):
        return can_use_assistant(request.user)


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user)
