from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LlmMessage:
    role: str
    content: str


@dataclass
class LlmResponse:
    text: str
    raw: dict[str, Any] = field(default_factory=dict)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: int | None = None
    model: str = ""
    provider: str = ""


class LlmClient(ABC):
    """Thin LLM wrapper for tool-internal calls (summarise / recommend)."""

    @abstractmethod
    def complete(
        self,
        messages: list[LlmMessage],
        *,
        system: str | None = None,
        purpose: str = "complete",
    ) -> LlmResponse:
        ...
