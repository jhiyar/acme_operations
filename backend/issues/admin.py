from django.contrib import admin

from issues.models import Customer, Issue, IssueUpdate, NextAction


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "tier", "industry", "account_owner")
    search_fields = ("name", "account_owner")


class IssueUpdateInline(admin.TabularInline):
    model = IssueUpdate
    extra = 0


class NextActionInline(admin.TabularInline):
    model = NextAction
    extra = 0


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "customer",
        "status",
        "priority",
        "assigned_to",
        "updated_at",
    )
    list_filter = ("status", "priority", "assigned_to")
    search_fields = ("title", "customer__name", "assigned_to")
    inlines = [IssueUpdateInline, NextActionInline]


@admin.register(IssueUpdate)
class IssueUpdateAdmin(admin.ModelAdmin):
    list_display = ("id", "issue", "author", "created_at")


@admin.register(NextAction)
class NextActionAdmin(admin.ModelAdmin):
    list_display = ("id", "issue", "status", "recommended_by", "created_at")
