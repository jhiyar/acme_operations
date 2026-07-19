import uuid

from django.db import models


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner_sub = models.CharField(max_length=64, db_index=True)
    title = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_conversation"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.title or f"Conversation {self.pk}"


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField()
    tool_trace = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_message"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.role} in {self.conversation_id}"


class AgentRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="runs",
    )
    owner_sub = models.CharField(max_length=64, db_index=True)
    username = models.CharField(max_length=120, blank=True, default="")
    user_message = models.TextField()
    assistant_reply = models.TextField(blank=True, default="")
    provider = models.CharField(max_length=40, blank=True, default="")
    model = models.CharField(max_length=120, blank=True, default="")
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    tool_count = models.PositiveIntegerField(default=0)
    llm_call_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True, default="")
    trace_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_agent_run"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Run {self.pk} by {self.username or self.owner_sub}"


class LlmCall(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        AgentRun,
        on_delete=models.CASCADE,
        related_name="llm_calls",
        null=True,
        blank=True,
    )
    provider = models.CharField(max_length=40)
    model = models.CharField(max_length=120)
    purpose = models.CharField(max_length=64, blank=True, default="complete")
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    request_id = models.CharField(max_length=120, blank=True, default="")
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_llm_call"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.provider}/{self.model} ({self.total_tokens} tok)"


class ToolCall(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        AgentRun,
        on_delete=models.CASCADE,
        related_name="tool_calls",
    )
    tool = models.CharField(max_length=120)
    args = models.JSONField(default=dict, blank=True)
    result_preview = models.TextField(blank=True, default="")
    sequence = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_tool_call"
        ordering = ["sequence", "created_at"]

    def __str__(self) -> str:
        return f"{self.tool}#{self.sequence}"
