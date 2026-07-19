from __future__ import annotations

import time
from typing import Any

from django.conf import settings

from core.services.llm.base import LlmClient, LlmMessage, LlmResponse
from core.services.llm_logging import (
    record_llm_call,
    reset_llm_purpose,
    set_llm_purpose,
    usage_from_anthropic,
)


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
        purpose: str = "complete",
    ) -> LlmResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if system:
            kwargs["system"] = system

        purpose_token = set_llm_purpose(purpose)
        started = time.perf_counter()
        try:
            response = self.client.messages.create(**kwargs)
            latency_ms = int((time.perf_counter() - started) * 1000)
            parts = [
                block.text
                for block in response.content
                if getattr(block, "type", None) == "text"
            ]
            prompt, completion, total = usage_from_anthropic(response)
            request_id = str(getattr(response, "id", "") or "")
            record_llm_call(
                provider="anthropic",
                model=self.model,
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=total,
                latency_ms=latency_ms,
                request_id=request_id,
                purpose=purpose,
            )
            return LlmResponse(
                text="\n".join(parts).strip(),
                raw={"id": request_id or None},
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=total,
                latency_ms=latency_ms,
                model=self.model,
                provider="anthropic",
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            record_llm_call(
                provider="anthropic",
                model=self.model,
                latency_ms=latency_ms,
                purpose=purpose,
                error=str(exc),
            )
            raise
        finally:
            reset_llm_purpose(purpose_token)
