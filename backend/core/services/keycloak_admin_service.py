from __future__ import annotations

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger("acme.keycloak_admin")

APP_ROLES = ("sales_user", "support_user", "admin")


class KeycloakAdminError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class KeycloakAdminService:
    """
    Manage users in the Acme Keycloak realm via the Admin REST API.

    Local demo auth: password grant against the master `admin-cli` client
    (compose bootstrap admin). Identities stay in Keycloak — no local users table.
    """

    def __init__(self) -> None:
        self.server_url = settings.KEYCLOAK_SERVER_URL.rstrip("/")
        self.realm = settings.KEYCLOAK_REALM
        self.admin_realm = getattr(settings, "KEYCLOAK_ADMIN_REALM", "master")
        self.admin_client_id = getattr(settings, "KEYCLOAK_ADMIN_CLIENT_ID", "admin-cli")
        self.admin_username = getattr(settings, "KEYCLOAK_ADMIN_USERNAME", "admin")
        self.admin_password = getattr(settings, "KEYCLOAK_ADMIN_PASSWORD", "admin")
        self._token: str | None = None

    @property
    def admin_base(self) -> str:
        return f"{self.server_url}/admin/realms/{self.realm}"

    def _token_url(self) -> str:
        return (
            f"{self.server_url}/realms/{self.admin_realm}"
            "/protocol/openid-connect/token"
        )

    def _get_token(self) -> str:
        if self._token:
            return self._token
        response = requests.post(
            self._token_url(),
            data={
                "grant_type": "password",
                "client_id": self.admin_client_id,
                "username": self.admin_username,
                "password": self.admin_password,
            },
            timeout=10,
        )
        if response.status_code >= 400:
            raise KeycloakAdminError(
                "Unable to authenticate to Keycloak Admin API",
                status_code=503,
            )
        self._token = response.json()["access_token"]
        return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | list | None = None,
        params: dict | None = None,
        expect_json: bool = True,
    ) -> Any:
        url = f"{self.admin_base}{path}"
        response = requests.request(
            method,
            url,
            headers=self._headers(),
            json=json,
            params=params,
            timeout=15,
        )
        if response.status_code == 401:
            self._token = None
            response = requests.request(
                method,
                url,
                headers=self._headers(),
                json=json,
                params=params,
                timeout=15,
            )
        if response.status_code >= 400:
            detail = self._error_detail(response)
            raise KeycloakAdminError(detail, status_code=response.status_code)
        if response.status_code == 204 or not expect_json or not response.content:
            return None
        return response.json()

    @staticmethod
    def _error_detail(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text or f"Keycloak error ({response.status_code})"
        if isinstance(payload, dict):
            return (
                payload.get("errorMessage")
                or payload.get("error_description")
                or payload.get("error")
                or str(payload)
            )
        return str(payload)

    def list_users(self) -> list[dict[str, Any]]:
        users = self._request("GET", "/users", params={"max": 200}) or []
        result = []
        for user in users:
            result.append(self._to_dict(user, roles=self._realm_roles(user["id"])))
        return result

    def get_user(self, user_id: str) -> dict[str, Any]:
        user = self._request("GET", f"/users/{user_id}")
        if not user:
            raise KeycloakAdminError("User not found", status_code=404)
        return self._to_dict(user, roles=self._realm_roles(user_id))

    def create_user(
        self,
        *,
        username: str,
        email: str = "",
        first_name: str = "",
        last_name: str = "",
        password: str,
        role: str,
        enabled: bool = True,
    ) -> dict[str, Any]:
        role = self._validate_role(role)
        username = username.strip()
        if not username:
            raise KeycloakAdminError("Username is required")
        if not password:
            raise KeycloakAdminError("Password is required")

        payload = {
            "username": username,
            "enabled": enabled,
            "email": (email or "").strip(),
            "emailVerified": True,
            "firstName": (first_name or "").strip(),
            "lastName": (last_name or "").strip(),
            "credentials": [
                {
                    "type": "password",
                    "value": password,
                    "temporary": False,
                }
            ],
        }
        response = requests.post(
            f"{self.admin_base}/users",
            headers=self._headers(),
            json=payload,
            timeout=15,
        )
        if response.status_code == 401:
            self._token = None
            response = requests.post(
                f"{self.admin_base}/users",
                headers=self._headers(),
                json=payload,
                timeout=15,
            )
        if response.status_code >= 400:
            raise KeycloakAdminError(
                self._error_detail(response),
                status_code=response.status_code,
            )

        location = response.headers.get("Location", "")
        user_id = location.rstrip("/").split("/")[-1] if location else ""
        if not user_id:
            # Fallback lookup
            matches = self._request(
                "GET", "/users", params={"username": username, "exact": "true"}
            ) or []
            if not matches:
                raise KeycloakAdminError("User created but id could not be resolved")
            user_id = matches[0]["id"]

        self._replace_app_roles(user_id, role)
        return self.get_user(user_id)

    def update_user(
        self,
        user_id: str,
        *,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        password: str | None = None,
        role: str | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        current = self._request("GET", f"/users/{user_id}")
        if not current:
            raise KeycloakAdminError("User not found", status_code=404)

        if email is not None:
            current["email"] = email.strip()
        if first_name is not None:
            current["firstName"] = first_name.strip()
        if last_name is not None:
            current["lastName"] = last_name.strip()
        if enabled is not None:
            current["enabled"] = enabled

        self._request("PUT", f"/users/{user_id}", json=current, expect_json=False)

        if password:
            self._request(
                "PUT",
                f"/users/{user_id}/reset-password",
                json={
                    "type": "password",
                    "value": password,
                    "temporary": False,
                },
                expect_json=False,
            )

        if role is not None:
            self._replace_app_roles(user_id, self._validate_role(role))

        return self.get_user(user_id)

    def delete_user(self, user_id: str) -> None:
        self._request("DELETE", f"/users/{user_id}", expect_json=False)

    def _realm_roles(self, user_id: str) -> list[str]:
        mappings = self._request("GET", f"/users/{user_id}/role-mappings/realm") or []
        names = {item.get("name") for item in mappings if item.get("name")}
        return sorted(name for name in names if name in APP_ROLES)

    def _role_representation(self, role_name: str) -> dict[str, Any]:
        role = self._request("GET", f"/roles/{role_name}")
        if not role:
            raise KeycloakAdminError(f"Role “{role_name}” not found", status_code=404)
        return role

    def _replace_app_roles(self, user_id: str, role_name: str) -> None:
        current = self._request("GET", f"/users/{user_id}/role-mappings/realm") or []
        to_remove = [item for item in current if item.get("name") in APP_ROLES]
        if to_remove:
            self._request(
                "DELETE",
                f"/users/{user_id}/role-mappings/realm",
                json=to_remove,
                expect_json=False,
            )
        role = self._role_representation(role_name)
        self._request(
            "POST",
            f"/users/{user_id}/role-mappings/realm",
            json=[role],
            expect_json=False,
        )

    @staticmethod
    def _validate_role(role: str) -> str:
        cleaned = (role or "").strip()
        if cleaned not in APP_ROLES:
            raise KeycloakAdminError(
                f"Role must be one of: {', '.join(APP_ROLES)}",
            )
        return cleaned

    @staticmethod
    def _to_dict(user: dict[str, Any], *, roles: list[str]) -> dict[str, Any]:
        return {
            "id": user.get("id"),
            "username": user.get("username") or "",
            "email": user.get("email") or "",
            "first_name": user.get("firstName") or "",
            "last_name": user.get("lastName") or "",
            "enabled": bool(user.get("enabled", True)),
            "roles": roles,
        }
