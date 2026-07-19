from django.contrib import admin

from core.models import AgentRun, Conversation, LlmCall, Message, ToolCall


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("role", "content", "tool_trace", "created_at")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "owner_sub", "updated_at")
    search_fields = ("title", "owner_sub")
    inlines = [MessageInline]


class LlmCallInline(admin.TabularInline):
    model = LlmCall
    extra = 0
    readonly_fields = (
        "provider",
        "model",
        "purpose",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "latency_ms",
        "created_at",
    )


class ToolCallInline(admin.TabularInline):
    model = ToolCall
    extra = 0
    readonly_fields = ("tool", "args", "result_preview", "sequence", "created_at")


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "username",
        "provider",
        "model",
        "total_tokens",
        "latency_ms",
        "created_at",
    )
    search_fields = ("username", "owner_sub", "trace_id")
    list_filter = ("provider",)
    inlines = [LlmCallInline, ToolCallInline]
