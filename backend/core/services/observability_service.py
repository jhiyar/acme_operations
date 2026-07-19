from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from django.conf import settings

from core.services.memory_service import MemoryService

logger = logging.getLogger("acme.observability")


@dataclass
class RequestTrace:
    trace_id: str
    user: str
    message: str
    started_at: str
    ended_at: str | None = None
    latency_ms: int | None = None
    reply: str | None = None
    error: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


class ObservabilityService:
    """
    Request/tool traces, latency, and error logs.

    Traces are written to Redis (short TTL) and optionally to disk under evals/traces/.
    """

    def __init__(self, memory: MemoryService | None = None) -> None:
        self.memory = memory or MemoryService()

    def start(self, *, user: str, message: str, meta: dict[str, Any] | None = None) -> RequestTrace:
        trace = RequestTrace(
            trace_id=str(uuid.uuid4()),
            user=user,
            message=message,
            started_at=datetime.now(timezone.utc).isoformat(),
            meta=meta or {},
        )
        logger.info("trace_start id=%s user=%s", trace.trace_id, user)
        return trace

    def record_tools(self, trace: RequestTrace, tool_trace: list[dict[str, Any]]) -> None:
        for step in tool_trace:
            entry = {
                "tool": step.get("tool"),
                "args": step.get("args"),
                "result_preview": str(step.get("result", ""))[:500],
            }
            trace.tool_calls.append(entry)
            logger.info(
                "tool_call id=%s tool=%s args=%s",
                trace.trace_id,
                entry["tool"],
                json.dumps(entry["args"], default=str)[:300],
            )

    def finish(
        self,
        trace: RequestTrace,
        *,
        reply: str | None = None,
        error: str | None = None,
        started_perf: float | None = None,
    ) -> RequestTrace:
        trace.ended_at = datetime.now(timezone.utc).isoformat()
        if started_perf is not None:
            trace.latency_ms = int((time.perf_counter() - started_perf) * 1000)
        trace.reply = reply
        trace.error = error
        if error:
            logger.error("trace_error id=%s error=%s", trace.trace_id, error)
        else:
            logger.info(
                "trace_end id=%s latency_ms=%s tools=%s",
                trace.trace_id,
                trace.latency_ms,
                [c.get("tool") for c in trace.tool_calls],
            )
        self._persist(trace)
        return trace

    def _persist(self, trace: RequestTrace) -> None:
        payload = asdict(trace)
        client = self.memory.client
        if client:
            key = f"acme:trace:{trace.trace_id}"
            client.setex(key, settings.REDIS_TRACE_TTL_SECONDS, json.dumps(payload, default=str))
            client.lpush("acme:traces", trace.trace_id)
            client.ltrim("acme:traces", 0, 199)

        if settings.OBSERVABILITY_WRITE_FILES:
            out_dir = Path(settings.BASE_DIR) / "evals" / "traces"
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{trace.trace_id}.json"
            path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
