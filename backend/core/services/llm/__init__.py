from __future__ import annotations

from typing import Any

from django.conf import settings

from core.services.llm.anthropic_llm_service import AnthropicLlmService
from core.services.llm.base import LlmClient
from core.services.llm.openai_llm_service import OpenAiCompatibleLlmService


def get_llm_client(provider: str | None = None) -> LlmClient:
    """Factory for tool-internal LLM calls (summarise / recommend)."""
    name = (provider or settings.LLM_PROVIDER).strip().lower()
    if name == "openai":
        return OpenAiCompatibleLlmService()
    if name == "anthropic":
        return AnthropicLlmService()
    raise ValueError(f"Unsupported LLM_PROVIDER: {name}")


def get_chat_model(provider: str | None = None) -> Any:
    """LangChain chat model used by the ReAct agent orchestrator."""
    name = (provider or settings.LLM_PROVIDER).strip().lower()
    if name == "anthropic":
        from langchain_anthropic import ChatAnthropic

        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        return ChatAnthropic(
            model=settings.ANTHROPIC_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=0,
        )
    if name == "openai":
        from langchain_openai import ChatOpenAI

        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        kwargs: dict[str, Any] = {
            "model": settings.OPENAI_MODEL,
            "api_key": settings.OPENAI_API_KEY,
            "temperature": 0,
        }
        base_url = getattr(settings, "OPENAI_BASE_URL", "") or None
        if base_url:
            kwargs["base_url"] = base_url
        return ChatOpenAI(**kwargs)
    raise ValueError(f"Unsupported LLM_PROVIDER: {name}")
