from __future__ import annotations

from typing import Any

from django.conf import settings

from core.services.llm.base import LlmClient, LlmMessage, LlmResponse


class AnthropicLlmService(LlmClient):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.ANTHROPIC_API_KEY
        self.model = model or settings.ANTHROPIC_MODEL
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            from anthropic import Anthropic

            if not self.api_key:
                raise RuntimeError("ANTHROPIC_API_KEY is not configured")
            self._client = Anthropic(api_key=self.api_key)
        return self._client

    def complete(
        self,
        messages: list[LlmMessage],
        *,
        system: str | None = None,
    ) -> LlmResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if system:
            kwargs["system"] = system

        response = self.client.messages.create(**kwargs)
        parts = [
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        ]
        return LlmResponse(text="\n".join(parts).strip(), raw={"id": getattr(response, "id", None)})
