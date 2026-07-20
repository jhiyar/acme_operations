from django.db import models


class Customer(models.Model):
    """
    Customer account.

    Table name keeps the legacy `core_customer` prefix from the initial schema
    before the issues app split — renaming would require a data migration.
    """
    name = models.CharField(max_length=255, unique=True)
    industry = models.CharField(max_length=120, blank=True)
    tier = models.CharField(max_length=40, default="standard")
    account_owner = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_customer"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Issue(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="issues",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    priority = models.CharField(
        max_length=32,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    assigned_to = models.CharField(max_length=120, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_issue"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"#{self.pk} {self.title}"


class IssueUpdate(models.Model):
    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name="updates",
    )
    author = models.CharField(max_length=120)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_issueupdate"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Update on issue #{self.issue_id} by {self.author}"


class NextAction(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name="next_actions",
    )
    summary = models.TextField()
    recommended_by = models.CharField(max_length=120)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_nextaction"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Next action for issue #{self.issue_id}"


class IssueHistorySummary(models.Model):
    """
    Durable LLM summary for an issue.

    Fingerprint tracks issue fields + timeline so a new update or next action
    forces a fresh summarise call instead of serving a stale brief.
    """

    issue = models.OneToOneField(
        Issue,
        on_delete=models.CASCADE,
        related_name="history_summary",
    )
    summary = models.TextField()
    fingerprint = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_issuehistorysummary"

    def __str__(self) -> str:
        return f"Summary for issue #{self.issue_id}"
