from __future__ import annotations

from typing import Any

from django.db.models import Prefetch, Q, QuerySet

from core.services.keycloak_auth_service import KeycloakUser
from issues.models import Customer, Issue, IssueUpdate, NextAction
from issues.permissions import can_manage_issues, can_update_issues, can_view_all_issues


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

    def get_for_user(self, user: KeycloakUser, issue_id: int) -> Issue | None:
        return self.visible_to(user).filter(pk=issue_id).first()

    @staticmethod
    def _fail(*, created: bool | None = None, updated: bool | None = None, deleted: bool | None = None, error: str, code: str = "bad_request") -> dict[str, Any]:
        payload: dict[str, Any] = {"error": error, "code": code}
        if created is not None:
            payload["created"] = created
        if updated is not None:
            payload["updated"] = updated
        if deleted is not None:
            payload["deleted"] = deleted
        return payload

    def create_issue(
        self,
        user: KeycloakUser,
        *,
        customer_id: int,
        title: str,
        description: str = "",
        status: str = Issue.Status.OPEN,
        priority: str = Issue.Priority.MEDIUM,
        assigned_to: str = "",
    ) -> dict[str, Any]:
        if not can_manage_issues(user):
            return self._fail(created=False, error="Only admin can create issues", code="forbidden")

        title = title.strip()
        if not title:
            return self._fail(created=False, error="Title is required")

        customer = Customer.objects.filter(pk=customer_id).first()
        if not customer:
            return self._fail(
                created=False,
                error=f"Customer #{customer_id} not found",
                code="not_found",
            )

        if status not in Issue.Status.values:
            return self._fail(created=False, error=f"Invalid status: {status}")
        if priority not in Issue.Priority.values:
            return self._fail(created=False, error=f"Invalid priority: {priority}")

        issue = Issue.objects.create(
            customer=customer,
            title=title,
            description=(description or "").strip(),
            status=status,
            priority=priority,
            assigned_to=(assigned_to or user.username).strip(),
        )
        return {"created": True, "issue": self.to_dict(issue, include_history=True)}

    def delete_issue(self, user: KeycloakUser, issue_id: int) -> dict[str, Any]:
        if not can_manage_issues(user):
            return self._fail(deleted=False, error="Only admin can delete issues", code="forbidden")

        issue = self.get_for_user(user, issue_id)
        if not issue:
            return self._fail(
                deleted=False,
                error=f"Issue #{issue_id} not found or not visible",
                code="not_found",
            )

        issue.delete()
        return {"deleted": True, "id": issue_id}

    def update_issue(
        self,
        user: KeycloakUser,
        issue_id: int,
        *,
        status: str | None = None,
        priority: str | None = None,
        assigned_to: str | None = None,
        title: str | None = None,
        description: str | None = None,
        customer_id: int | None = None,
    ) -> dict[str, Any]:
        if not can_update_issues(user):
            return self._fail(
                updated=False,
                error="Only support_user or admin can update issues",
                code="forbidden",
            )

        issue = self.get_for_user(user, issue_id)
        if not issue:
            return self._fail(
                updated=False,
                error=f"Issue #{issue_id} not found or not visible",
                code="not_found",
            )

        # Full field edits require admin; support may only touch workflow fields.
        if not can_manage_issues(user) and any(
            value is not None for value in (title, description, customer_id)
        ):
            return self._fail(
                updated=False,
                error="Only admin can change title, description, or customer",
                code="forbidden",
            )

        fields: list[str] = []
        if title is not None:
            cleaned = title.strip()
            if not cleaned:
                return self._fail(updated=False, error="Title is required")
            issue.title = cleaned
            fields.append("title")
        if description is not None:
            issue.description = description.strip()
            fields.append("description")
        if customer_id is not None:
            customer = Customer.objects.filter(pk=customer_id).first()
            if not customer:
                return self._fail(
                    updated=False,
                    error=f"Customer #{customer_id} not found",
                    code="not_found",
                )
            issue.customer_id = customer.id
            fields.append("customer_id")
        if status is not None:
            if status not in Issue.Status.values:
                return self._fail(updated=False, error=f"Invalid status: {status}")
            issue.status = status
            fields.append("status")
        if priority is not None:
            if priority not in Issue.Priority.values:
                return self._fail(updated=False, error=f"Invalid priority: {priority}")
            issue.priority = priority
            fields.append("priority")
        if assigned_to is not None:
            issue.assigned_to = assigned_to.strip()
            fields.append("assigned_to")

        if not fields:
            return self._fail(updated=False, error="No updatable fields provided")

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
            return self._fail(
                created=False,
                error="Only support_user or admin can post issue updates",
                code="forbidden",
            )

        text = (body or "").strip()
        if not text:
            return self._fail(created=False, error="Update body is required")

        issue = self.get_for_user(user, issue_id)
        if not issue:
            return self._fail(
                created=False,
                error=f"Issue #{issue_id} not found or not visible",
                code="not_found",
            )

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

    def delete_update(
        self,
        user: KeycloakUser,
        issue_id: int,
        update_id: int,
    ) -> dict[str, Any]:
        if not can_update_issues(user):
            return self._fail(
                deleted=False,
                error="Only support_user or admin can delete issue updates",
                code="forbidden",
            )

        issue = self.get_for_user(user, issue_id)
        if not issue:
            return self._fail(
                deleted=False,
                error=f"Issue #{issue_id} not found or not visible",
                code="not_found",
            )

        update = IssueUpdate.objects.filter(pk=update_id, issue=issue).first()
        if not update:
            return self._fail(
                deleted=False,
                error=f"Update #{update_id} not found on issue #{issue_id}",
                code="not_found",
            )

        update.delete()
        return {"deleted": True, "id": update_id, "issue_id": issue_id}

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
