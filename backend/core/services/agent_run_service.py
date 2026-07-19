from __future__ import annotations

from typing import Any
from uuid import UUID

from django.conf import settings
from django.db.models import Count, Prefetch, Sum

from core.models import AgentRun, Conversation, LlmCall, ToolCall
from core.services.keycloak_auth_service import KeycloakUser
from core.services.llm_logging import set_current_run_id, preview_tool_result


class AgentRunService:
    """Create and finalize durable agent run records for the admin UI."""

    def start(
        self,
        user: KeycloakUser,
        *,
        user_message: str,
        conversation: Conversation | None = None,
        trace_id: str = "",
    ) -> AgentRun:
        provider = (settings.LLM_PROVIDER or "").strip().lower()
        model = (
            settings.ANTHROPIC_MODEL
            if provider == "anthropic"
            else settings.OPENAI_MODEL
        )
        return AgentRun.objects.create(
            conversation=conversation,
            owner_sub=user.sub,
            username=user.username,
            user_message=user_message,
            provider=provider,
            model=model,
            trace_id=trace_id or "",
        )

    def bind(self, run: AgentRun):
        return set_current_run_id(run.id)

    def record_tools(self, run: AgentRun, tool_trace: list[dict[str, Any]]) -> None:
        ToolCall.objects.filter(run=run).delete()
        rows = [
            ToolCall(
                run=run,
                tool=str(step.get("tool") or "unknown"),
                args=step.get("args") if isinstance(step.get("args"), dict) else {},
                result_preview=preview_tool_result(
                    step.get("result") if step.get("result") is not None else ""
                ),
                sequence=index,
            )
            for index, step in enumerate(tool_trace)
        ]
        if rows:
            ToolCall.objects.bulk_create(rows)
        run.tool_count = len(rows)
        run.save(update_fields=["tool_count"])

    def finish(
        self,
        run: AgentRun,
        *,
        assistant_reply: str = "",
        latency_ms: int | None = None,
        error: str = "",
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> AgentRun:
        llm_agg = run.llm_calls.aggregate(
            prompt=Sum("prompt_tokens"),
            completion=Sum("completion_tokens"),
            total=Sum("total_tokens"),
            count=Count("id"),
        )

        run.assistant_reply = assistant_reply or ""
        run.latency_ms = latency_ms
        run.error = error or ""
        run.prompt_tokens = int(
            prompt_tokens
            if prompt_tokens is not None
            else (llm_agg.get("prompt") or run.prompt_tokens or 0)
        )
        run.completion_tokens = int(
            completion_tokens
            if completion_tokens is not None
            else (llm_agg.get("completion") or run.completion_tokens or 0)
        )
        run.total_tokens = int(
            total_tokens
            if total_tokens is not None
            else (llm_agg.get("total") or run.total_tokens or 0)
        )
        run.llm_call_count = int(llm_agg.get("count") or run.llm_call_count or 0)
        run.save(
            update_fields=[
                "assistant_reply",
                "latency_ms",
                "error",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "llm_call_count",
            ]
        )
        return run

    def list_runs(self, *, limit: int = 50) -> list[AgentRun]:
        return list(AgentRun.objects.all()[: max(1, min(limit, 200))])

    def get_run(self, run_id: UUID | str) -> AgentRun:
        return AgentRun.objects.prefetch_related(
            Prefetch("llm_calls", queryset=LlmCall.objects.all()),
            Prefetch("tool_calls", queryset=ToolCall.objects.all()),
        ).get(pk=run_id)

    def to_summary(self, run: AgentRun) -> dict[str, Any]:
        return {
            "id": str(run.id),
            "conversation_id": str(run.conversation_id) if run.conversation_id else None,
            "username": run.username,
            "owner_sub": run.owner_sub,
            "user_message": run.user_message[:240],
            "assistant_reply": (run.assistant_reply or "")[:240],
            "provider": run.provider,
            "model": run.model,
            "prompt_tokens": run.prompt_tokens,
            "completion_tokens": run.completion_tokens,
            "total_tokens": run.total_tokens,
            "latency_ms": run.latency_ms,
            "tool_count": run.tool_count,
            "llm_call_count": run.llm_call_count,
            "error": run.error,
            "trace_id": run.trace_id,
            "created_at": run.created_at.isoformat(),
        }

    def to_detail(self, run: AgentRun) -> dict[str, Any]:
        return {
            **self.to_summary(run),
            "user_message": run.user_message,
            "assistant_reply": run.assistant_reply,
            "llm_calls": [
                {
                    "id": str(call.id),
                    "provider": call.provider,
                    "model": call.model,
                    "purpose": call.purpose,
                    "prompt_tokens": call.prompt_tokens,
                    "completion_tokens": call.completion_tokens,
                    "total_tokens": call.total_tokens,
                    "latency_ms": call.latency_ms,
                    "request_id": call.request_id,
                    "error": call.error,
                    "created_at": call.created_at.isoformat(),
                }
                for call in run.llm_calls.all()
            ],
            "tool_calls": [
                {
                    "id": str(call.id),
                    "tool": call.tool,
                    "args": call.args,
                    "result_preview": call.result_preview,
                    "sequence": call.sequence,
                    "created_at": call.created_at.isoformat(),
                }
                for call in run.tool_calls.all()
            ],
        }
