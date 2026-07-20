from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from core.services.keycloak_admin_service import (
    KeycloakAdminError,
    KeycloakAdminService,
)
from core.services.keycloak_auth_service import KeycloakUser


def make_admin() -> KeycloakUser:
    return KeycloakUser(
        sub="sub-admin",
        username="admin",
        email="admin@acme.local",
        roles=["admin"],
    )


class KeycloakAdminServiceTests(SimpleTestCase):
    def test_validate_role(self) -> None:
        self.assertEqual(KeycloakAdminService._validate_role("admin"), "admin")
        with self.assertRaises(KeycloakAdminError):
            KeycloakAdminService._validate_role("superuser")

    def test_to_dict(self) -> None:
        data = KeycloakAdminService._to_dict(
            {
                "id": "abc",
                "username": "sales",
                "email": "sales@acme.local",
                "firstName": "Sam",
                "lastName": "Sales",
                "enabled": True,
            },
            roles=["sales_user"],
        )
        self.assertEqual(data["id"], "abc")
        self.assertEqual(data["roles"], ["sales_user"])
        self.assertEqual(data["first_name"], "Sam")


class UserApiPermissionTests(APITestCase):
    def test_non_admin_forbidden(self) -> None:
        user = KeycloakUser(
            sub="sub-sales",
            username="sales",
            email="sales@acme.local",
            roles=["sales_user"],
        )
        self.client.force_authenticate(user=user)
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("core.views.KeycloakAdminService")
    def test_admin_lists_users(self, service_cls: MagicMock) -> None:
        service_cls.return_value.list_users.return_value = [
            {
                "id": "1",
                "username": "sales",
                "email": "sales@acme.local",
                "first_name": "Sam",
                "last_name": "Sales",
                "enabled": True,
                "roles": ["sales_user"],
            }
        ]
        self.client.force_authenticate(user=make_admin())
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    @patch("core.views.KeycloakAdminService")
    def test_admin_cannot_delete_self(self, service_cls: MagicMock) -> None:
        self.client.force_authenticate(user=make_admin())
        response = self.client.delete("/api/users/sub-admin/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        service_cls.return_value.delete_user.assert_not_called()
