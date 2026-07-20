from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.permissions import BasePermission

from core.permissions import is_admin, is_support

if TYPE_CHECKING:
    from core.services.keycloak_auth_service import KeycloakUser


def can_view_all_issues(user: KeycloakUser | None) -> bool:
    return is_admin(user)


def can_update_issues(user: KeycloakUser | None) -> bool:
    """support_user and admin may change status / post timeline notes."""
    return is_admin(user) or is_support(user)


def can_manage_issues(user: KeycloakUser | None) -> bool:
    """Create / delete / full field edit — admin only for this prototype."""
    return is_admin(user)


def can_manage_customers(user: KeycloakUser | None) -> bool:
    """Create / update / delete customer profiles — admin only."""
    return is_admin(user)


def can_create_next_action(user: KeycloakUser | None) -> bool:
    """Same gate as workflow updates: support + admin."""
    return can_update_issues(user)


class CanUpdateIssues(BasePermission):
    """support_user and admin may update issues / post timeline notes."""

    def has_permission(self, request, view):
        return can_update_issues(request.user)


class CanManageIssues(BasePermission):
    """admin may create, fully edit, and delete issues."""

    def has_permission(self, request, view):
        return can_manage_issues(request.user)


class CanManageCustomers(BasePermission):
    """admin may create, edit, and delete customers."""

    def has_permission(self, request, view):
        return can_manage_customers(request.user)
