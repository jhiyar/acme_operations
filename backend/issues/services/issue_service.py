from __future__ import annotations

from typing import Any

from django.db.models import Prefetch, Q, QuerySet

from core.permissions import can_update_issues, can_view_all_issues
from core.services.keycloak_auth_service import KeycloakUser
from issues.models import Issue, IssueUpdate, NextAction


class IssueService:
    OPEN_STATUSES = (Issue.Status.OPEN, Issue.Status.IN_PROGRESS)

    def visible_to(self, user: KeycloakUser) -> QuerySet[Issue]:
        qs = Issue.objects.select_related("customer").prefetch_related(
            Prefetch("updates", queryset=IssueUpdate.objects.order_by("created_at")),
            Prefetch(
                "next_actions",
                queryset=NextAction.objects.order_by("-created_at"),
            ),
        )
        if can_view_all_issues(user):
            return qs
        return qs.filter(assigned_to__iexact=user.username)

    def list_for_user(
        self,
        user: KeycloakUser,
        *,
        status: str | None = None,
        customer_name: str | None = None,
    ) -> list[dict[str, Any]]:
        qs = self.visible_to(user)
        if status:
            qs = qs.filter(status=status)
        if customer_name:
            qs = qs.filter(customer__name__iexact=customer_name.strip())
        return [self.to_dict(issue) for issue in qs]

    def get_for_user(self, user: KeycloakUser, issue_id: int) -> Issue | None:
        return self.visible_to(user).filter(pk=issue_id).first()

    def update_issue(
        self,
        user: KeycloakUser,
        issue_id: int,
        *,
        status: str | None = None,
        priority: str | None = None,
        assigned_to: str | None = None,
    ) -> dict[str, Any]:
        if not can_update_issues(user):
            return {"updated": False, "error": "Only support_user or admin can update issues"}

        issue = self.get_for_user(user, issue_id)
        if not issue:
            return {"updated": False, "error": f"Issue #{issue_id} not found or not visible"}

        fields: list[str] = []
        if status is not None:
            if status not in Issue.Status.values:
                return {"updated": False, "error": f"Invalid status: {status}"}
            issue.status = status
            fields.append("status")
        if priority is not None:
            if priority not in Issue.Priority.values:
                return {"updated": False, "error": f"Invalid priority: {priority}"}
            issue.priority = priority
            fields.append("priority")
        if assigned_to is not None:
            issue.assigned_to = assigned_to.strip()
            fields.append("assigned_to")

        if not fields:
            return {"updated": False, "error": "No updatable fields provided"}

        fields.append("updated_at")
        issue.save(update_fields=fields)
        return {
            "updated": True,
            "issue": self.to_dict(issue, include_history=True),
        }

    def add_update(
        self,
        user: KeycloakUser,
        issue_id: int,
        *,
        body: str,
    ) -> dict[str, Any]:
        if not can_update_issues(user):
            return {
                "created": False,
                "error": "Only support_user or admin can post issue updates",
            }

        text = (body or "").strip()
        if not text:
            return {"created": False, "error": "Update body is required"}

        issue = self.get_for_user(user, issue_id)
        if not issue:
            return {"created": False, "error": f"Issue #{issue_id} not found or not visible"}

        update = IssueUpdate.objects.create(
            issue=issue,
            author=user.username,
            body=text,
        )
        return {
            "created": True,
            "update": {
                "id": update.id,
                "author": update.author,
                "body": update.body,
                "created_at": update.created_at.isoformat(),
            },
            "issue": self.to_dict(issue, include_history=True),
        }

    def open_issues_for_customer(
        self,
        customer_name: str,
        user: KeycloakUser | None = None,
    ) -> list[dict[str, Any]]:
        from issues.services.customer_service import CustomerService

        name = customer_name.strip()
        customer = CustomerService().get_by_name(name)
        if customer:
            qs = Issue.objects.select_related("customer").filter(
                customer=customer,
                status__in=self.OPEN_STATUSES,
            )
        else:
            # Keyword fallback: title/description match (e.g. "Client X")
            qs = Issue.objects.select_related("customer").filter(
                status__in=self.OPEN_STATUSES,
            ).filter(
                Q(title__icontains=name)
                | Q(description__icontains=name)
                | Q(customer__name__icontains=name)
            )
        if user and not can_view_all_issues(user):
            qs = qs.filter(assigned_to__iexact=user.username)
        return [self.to_dict(issue) for issue in qs]

    def to_dict(self, issue: Issue, *, include_history: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": issue.id,
            "title": issue.title,
            "description": issue.description,
            "status": issue.status,
            "priority": issue.priority,
            "assigned_to": issue.assigned_to,
            "customer": {
                "id": issue.customer_id,
                "name": issue.customer.name,
            },
            "created_at": issue.created_at.isoformat(),
            "updated_at": issue.updated_at.isoformat(),
        }
        if include_history:
            data["updates"] = [
                {
                    "id": update.id,
                    "author": update.author,
                    "body": update.body,
                    "created_at": update.created_at.isoformat(),
                }
                for update in issue.updates.all()
            ]
            data["next_actions"] = [
                {
                    "id": action.id,
                    "summary": action.summary,
                    "recommended_by": action.recommended_by,
                    "status": action.status,
                    "created_at": action.created_at.isoformat(),
                }
                for action in issue.next_actions.all()
            ]
        return data
