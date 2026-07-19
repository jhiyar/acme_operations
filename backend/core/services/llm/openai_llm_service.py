from __future__ import annotations

import time
from typing import Any

from django.conf import settings

from core.services.llm.base import LlmClient, LlmMessage, LlmResponse
from core.services.llm_logging import (
    record_llm_call,
    reset_llm_purpose,
    set_llm_purpose,
    usage_from_openai,
)


class OpenAiCompatibleLlmService(LlmClient):
    """OpenAI SDK client with optional base_url (OpenAI, Azure, local proxies)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
        self.base_url = (
            base_url if base_url is not None else getattr(settings, "OPENAI_BASE_URL", "") or None
        )
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            if not self.api_key:
                raise RuntimeError("OPENAI_API_KEY is not configured")
            kwargs: dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def complete(
        self,
        messages: list[LlmMessage],
        *,
        system: str | None = None,
        purpose: str = "complete",
    ) -> LlmResponse:
        payload: list[dict[str, str]] = []
        if system:
            payload.append({"role": "system", "content": system})
        payload.extend({"role": m.role, "content": m.content} for m in messages)

        purpose_token = set_llm_purpose(purpose)
        started = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=payload,
                max_tokens=1024,
            )
            latency_ms = int((time.perf_counter() - started) * 1000)
            choice = response.choices[0].message
            prompt, completion, total = usage_from_openai(response)
            request_id = str(getattr(response, "id", "") or "")
            record_llm_call(
                provider="openai",
                model=self.model,
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=total,
                latency_ms=latency_ms,
                request_id=request_id,
                purpose=purpose,
            )
            return LlmResponse(
                text=(choice.content or "").strip(),
                raw={"id": request_id or None},
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=total,
                latency_ms=latency_ms,
                model=self.model,
                provider="openai",
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            record_llm_call(
                provider="openai",
                model=self.model,
                latency_ms=latency_ms,
                purpose=purpose,
                error=str(exc),
            )
            raise
        finally:
            reset_llm_purpose(purpose_token)
