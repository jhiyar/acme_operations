from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

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


def can_view_all_issues(user: KeycloakUser | None) -> bool:
    return is_admin(user)


def can_create_next_action(user: KeycloakUser | None) -> bool:
    return is_admin(user) or is_support(user)


def can_update_issues(user: KeycloakUser | None) -> bool:
    return is_admin(user) or is_support(user)
