from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis
from django.conf import settings

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Redis short-term memory.

    Postgres remains the source of truth for customers/issues/summaries.
    Redis holds conversation turns, cached customer lookups, and recent
    read-only tool results (short TTL).
    """

    def __init__(self, client: redis.Redis | None = None) -> None:
        self._client = client
        self._enabled = True
        self._connect_attempted = client is not None

    @property
    def client(self) -> redis.Redis | None:
        if self._client is not None:
            return self._client
        if self._connect_attempted and not self._enabled:
            return None
        self._connect_attempted = True
        try:
            self._client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1,
                socket_timeout=1,
            )
            self._client.ping()
            return self._client
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis unavailable; memory disabled: %s", exc)
            self._enabled = False
            self._client = None
            return None

    @property
    def enabled(self) -> bool:
        return self._enabled and self.client is not None

    def session_key(self, user_sub: str, session_id: str | None = None) -> str:
        sid = session_id or "default"
        return f"acme:session:{user_sub}:{sid}"

    def append_turn(
        self,
        user_sub: str,
        role: str,
        content: str,
        *,
        session_id: str | None = None,
        tool_trace: list[dict[str, Any]] | None = None,
    ) -> None:
        client = self.client
        if not client:
            return
        key = self.session_key(user_sub, session_id)
        payload = {
            "role": role,
            "content": content,
            "tool_trace": tool_trace or [],
        }
        client.rpush(key, json.dumps(payload))
        client.ltrim(key, -settings.REDIS_SESSION_MAX_TURNS, -1)
        client.expire(key, settings.REDIS_SESSION_TTL_SECONDS)

    def get_history(
        self,
        user_sub: str,
        *,
        session_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        client = self.client
        if not client:
            return []
        key = self.session_key(user_sub, session_id)
        raw = client.lrange(key, 0, -1)
        turns = [json.loads(item) for item in raw]
        if limit:
            return turns[-limit:]
        return turns

    def cache_customer(self, customer_name: str, data: dict[str, Any]) -> None:
        client = self.client
        if not client:
            return
        key = f"acme:cache:customer:{customer_name.strip().lower()}"
        client.setex(key, settings.REDIS_CACHE_TTL_SECONDS, json.dumps(data, default=str))

    def get_cached_customer(self, customer_name: str) -> dict[str, Any] | None:
        client = self.client
        if not client:
            return None
        key = f"acme:cache:customer:{customer_name.strip().lower()}"
        raw = client.get(key)
        return json.loads(raw) if raw else None

    @staticmethod
    def tool_cache_key(**parts: Any) -> str:
        raw = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:40]

    def cache_tool_result(self, tool: str, cache_key: str, data: dict[str, Any]) -> None:
        client = self.client
        if not client:
            return
        key = f"acme:tool:{tool}:{cache_key}"
        client.setex(
            key,
            settings.REDIS_TOOL_TTL_SECONDS,
            json.dumps(data, default=str),
        )

    def get_cached_tool_result(self, tool: str, cache_key: str) -> dict[str, Any] | None:
        client = self.client
        if not client:
            return None
        key = f"acme:tool:{tool}:{cache_key}"
        raw = client.get(key)
        return json.loads(raw) if raw else None
