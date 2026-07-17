from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import jwt
import requests
from django.conf import settings
from jwt import PyJWKClient


@dataclass
class KeycloakUser:
    sub: str
    username: str
    email: str = ""
    roles: list[str] = field(default_factory=list)
    claims: dict[str, Any] = field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def __str__(self) -> str:
        return self.username


class KeycloakAuthService:
    """Verify Keycloak JWTs using the realm JWKS endpoint."""

    def __init__(self) -> None:
        # Internal URL used to reach Keycloak from this process (may be a Docker service name).
        self.server_url = settings.KEYCLOAK_SERVER_URL.rstrip("/")
        # Public issuer embedded in tokens (browser-facing host, e.g. localhost).
        self.issuer_base = getattr(
            settings, "KEYCLOAK_ISSUER_URL", settings.KEYCLOAK_SERVER_URL
        ).rstrip("/")
        self.realm = settings.KEYCLOAK_REALM
        self.client_id = settings.KEYCLOAK_CLIENT_ID
        self.audience = getattr(settings, "KEYCLOAK_AUDIENCE", self.client_id)
        self._jwks_client: PyJWKClient | None = None

    @property
    def issuer(self) -> str:
        return f"{self.issuer_base}/realms/{self.realm}"

    @property
    def jwks_url(self) -> str:
        return f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/certs"

    @property
    def token_url(self) -> str:
        return f"{self.issuer_base}/realms/{self.realm}/protocol/openid-connect/token"

    def _get_jwks_client(self) -> PyJWKClient:
        if self._jwks_client is None:
            self._jwks_client = PyJWKClient(self.jwks_url)
        return self._jwks_client

    def verify_token(self, token: str) -> KeycloakUser:
        signing_key = self._get_jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=self.audience,
            issuer=self.issuer,
            options={"verify_aud": False},
        )

        # Prefer azp/client audience check when aud is not the client id
        azp = payload.get("azp")
        aud = payload.get("aud")
        if azp and azp != self.client_id:
            if isinstance(aud, str) and aud != self.client_id:
                raise ValueError("Token was not issued for this client")
            if isinstance(aud, list) and self.client_id not in aud:
                raise ValueError("Token was not issued for this client")

        roles = self._extract_roles(payload)
        username = (
            payload.get("preferred_username") or payload.get("email") or "user"
        )
        return KeycloakUser(
            sub=payload.get("sub") or username,
            username=username,
            email=payload.get("email", ""),
            roles=roles,
            claims=payload,
        )

    def _extract_roles(self, payload: dict[str, Any]) -> list[str]:
        realm_roles = payload.get("realm_access", {}).get("roles", []) or []
        client_roles = (
            payload.get("resource_access", {}).get(self.client_id, {}).get("roles", [])
            or []
        )
        return sorted(set(realm_roles) | set(client_roles))

    def health(self) -> dict[str, Any]:
        try:
            response = requests.get(
                f"{self.server_url}/realms/{self.realm}/.well-known/openid-configuration",
                timeout=3,
            )
            response.raise_for_status()
            return {
                "status": "ok",
                "issuer": self.issuer,
                "jwks_url": self.jwks_url,
            }
        except requests.RequestException as exc:
            return {
                "status": "unavailable",
                "issuer": self.issuer,
                "jwks_url": self.jwks_url,
                "error": str(exc),
            }
