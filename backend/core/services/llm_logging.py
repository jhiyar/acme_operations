from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from typing import Any
from uuid import UUID

from django.db.models import F

logger = logging.getLogger("acme.llm")

_current_run_id: ContextVar[UUID | None] = ContextVar("acme_agent_run_id", default=None)
_current_purpose: ContextVar[str] = ContextVar("acme_llm_purpose", default="complete")


def set_current_run_id(run_id: UUID | None):
    return _current_run_id.set(run_id)


def reset_current_run_id(token) -> None:
    _current_run_id.reset(token)


def get_current_run_id() -> UUID | None:
    return _current_run_id.get()


def set_llm_purpose(purpose: str):
    return _current_purpose.set(purpose)


def reset_llm_purpose(token) -> None:
    _current_purpose.reset(token)


def get_llm_purpose() -> str:
    return _current_purpose.get() or "complete"


def record_llm_call(
    *,
    provider: str,
    model: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    latency_ms: int | None = None,
    request_id: str = "",
    purpose: str | None = None,
    error: str = "",
    run_id: UUID | None = None,
) -> Any | None:
    """Persist + log an LLM call. Safe no-op if DB unavailable."""
    effective_purpose = purpose or get_llm_purpose()
    effective_run_id = run_id or get_current_run_id()
    prompt_tokens = int(prompt_tokens or 0)
    completion_tokens = int(completion_tokens or 0)
    total_tokens = int(total_tokens or (prompt_tokens + completion_tokens))

    logger.info(
        "llm_call provider=%s model=%s purpose=%s prompt=%s completion=%s total=%s "
        "latency_ms=%s request_id=%s run_id=%s error=%s",
        provider,
        model,
        effective_purpose,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        latency_ms,
        request_id or "-",
        effective_run_id or "-",
        error or "-",
    )

    try:
        from core.models import AgentRun, LlmCall

        run = None
        if effective_run_id:
            run = AgentRun.objects.filter(pk=effective_run_id).first()

        call = LlmCall.objects.create(
            run=run,
            provider=provider,
            model=model,
            purpose=effective_purpose,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            request_id=request_id or "",
            error=error or "",
        )
        if run is not None:
            AgentRun.objects.filter(pk=run.pk).update(
                prompt_tokens=F("prompt_tokens") + prompt_tokens,
                completion_tokens=F("completion_tokens") + completion_tokens,
                total_tokens=F("total_tokens") + total_tokens,
                llm_call_count=F("llm_call_count") + 1,
            )
        return call
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to persist LLM call: %s", exc)
        return None


def truncate_text(value: Any, limit: int = 2000) -> str:
    text = value if isinstance(value, str) else str(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def preview_tool_result(value: Any, limit: int = 6000) -> str:
    """Pretty-print JSON tool results before truncating for storage/UI."""
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    trimmed = text.strip()
    if not trimmed:
        return ""
    try:
        parsed = json.loads(trimmed)
        pretty = json.dumps(parsed, indent=2, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        pretty = text
    if len(pretty) <= limit:
        return pretty
    return f"{pretty[: limit - 1]}…"


def usage_from_anthropic(response: Any) -> tuple[int, int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0, 0
    prompt = int(getattr(usage, "input_tokens", 0) or 0)
    completion = int(getattr(usage, "output_tokens", 0) or 0)
    return prompt, completion, prompt + completion


def usage_from_openai(response: Any) -> tuple[int, int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0, 0
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    total = int(getattr(usage, "total_tokens", 0) or (prompt + completion))
    return prompt, completion, total


def usage_from_ai_message(message: Any) -> tuple[int, int, int]:
    meta = getattr(message, "usage_metadata", None) or {}
    if isinstance(meta, dict) and meta:
        prompt = int(meta.get("input_tokens") or meta.get("prompt_tokens") or 0)
        completion = int(meta.get("output_tokens") or meta.get("completion_tokens") or 0)
        total = int(meta.get("total_tokens") or (prompt + completion))
        return prompt, completion, total

    response_meta = getattr(message, "response_metadata", None) or {}
    usage = response_meta.get("usage") if isinstance(response_meta, dict) else None
    if isinstance(usage, dict):
        prompt = int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
        completion = int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        total = int(usage.get("total_tokens") or (prompt + completion))
        return prompt, completion, total
    return 0, 0, 0
