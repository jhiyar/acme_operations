from __future__ import annotations

from django.test import TestCase

from issues.models import Customer, Issue, IssueUpdate
from issues.services import CustomerService, IssueService
from core.services.keycloak_auth_service import KeycloakUser


def make_user(username: str, *roles: str) -> KeycloakUser:
    return KeycloakUser(
        sub=f"sub-{username}",
        username=username,
        email=f"{username}@example.com",
        roles=list(roles),
    )


class CustomerServiceTests(TestCase):
    def setUp(self) -> None:
        self.service = CustomerService()
        self.customer = Customer.objects.create(
            name="Contoso Ltd",
            industry="Manufacturing",
            tier="premium",
            account_owner="sales",
            contact_email="support@contoso.example",
            notes="Seed note",
        )

    def test_get_by_name_case_insensitive(self) -> None:
        found = self.service.get_by_name("contoso ltd")
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found.pk, self.customer.pk)

    def test_get_by_name_partial_match(self) -> None:
        found = self.service.get_by_name("Contoso")
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found.pk, self.customer.pk)

    def test_get_by_name_missing(self) -> None:
        self.assertIsNone(self.service.get_by_name("Missing Co"))

    def test_to_dict(self) -> None:
        data = self.service.to_dict(self.customer)
        self.assertEqual(data["name"], "Contoso Ltd")
        self.assertEqual(data["tier"], "premium")

    def test_admin_can_create_update_delete(self) -> None:
        admin = make_user("admin", "admin")
        created = self.service.create_customer(
            admin,
            name="Northwind",
            industry="Trading",
            tier="standard",
        )
        self.assertTrue(created["created"])
        customer_id = created["customer"]["id"]

        updated = self.service.update_customer(
            admin,
            customer_id,
            tier="premium",
            notes="VIP",
        )
        self.assertTrue(updated["updated"])
        self.assertEqual(updated["customer"]["tier"], "premium")

        deleted = self.service.delete_customer(admin, customer_id)
        self.assertTrue(deleted["deleted"])
        self.assertFalse(Customer.objects.filter(pk=customer_id).exists())

    def test_cannot_delete_customer_with_issues(self) -> None:
        admin = make_user("admin", "admin")
        Issue.objects.create(
            customer=self.customer,
            title="Open ticket",
            assigned_to="support",
        )
        result = self.service.delete_customer(admin, self.customer.id)
        self.assertFalse(result["deleted"])
        self.assertTrue(Customer.objects.filter(pk=self.customer.id).exists())

    def test_support_cannot_create_customer(self) -> None:
        support = make_user("support", "support_user")
        result = self.service.create_customer(support, name="Blocked Co")
        self.assertFalse(result["created"])


class IssueServiceTests(TestCase):
    def setUp(self) -> None:
        self.service = IssueService()
        self.customer = Customer.objects.create(name="Northwind Traders")
        self.open_issue = Issue.objects.create(
            customer=self.customer,
            title="Open shipment issue",
            description="Tracking gaps",
            status=Issue.Status.OPEN,
            priority=Issue.Priority.HIGH,
            assigned_to="sales",
        )
        self.other_issue = Issue.objects.create(
            customer=self.customer,
            title="Support-only issue",
            description="Firmware",
            status=Issue.Status.IN_PROGRESS,
            priority=Issue.Priority.CRITICAL,
            assigned_to="support",
        )
        IssueUpdate.objects.create(
            issue=self.open_issue,
            author="sales",
            body="Customer asked for ETA",
        )

    def test_admin_sees_all_issues(self) -> None:
        admin = make_user("admin", "admin")
        qs = self.service.visible_to(admin)
        self.assertEqual(qs.count(), 2)

    def test_sales_sees_only_assigned(self) -> None:
        sales = make_user("sales", "sales_user")
        qs = self.service.visible_to(sales)
        self.assertEqual(list(qs.values_list("id", flat=True)), [self.open_issue.id])

    def test_open_issues_for_customer(self) -> None:
        issues = self.service.open_issues_for_customer("Northwind Traders")
        self.assertEqual(len(issues), 2)
        self.assertTrue(all(i["status"] in ("open", "in_progress") for i in issues))

    def test_to_dict_includes_history(self) -> None:
        data = self.service.to_dict(self.open_issue, include_history=True)
        self.assertEqual(data["title"], "Open shipment issue")
        self.assertEqual(len(data["updates"]), 1)
        self.assertEqual(data["updates"][0]["body"], "Customer asked for ETA")

    def test_support_can_update_assigned_issue_status(self) -> None:
        support = make_user("support", "support_user")
        result = self.service.update_issue(
            support,
            self.other_issue.id,
            status=Issue.Status.RESOLVED,
        )
        self.assertTrue(result["updated"])
        self.other_issue.refresh_from_db()
        self.assertEqual(self.other_issue.status, Issue.Status.RESOLVED)

    def test_sales_cannot_update_issue(self) -> None:
        sales = make_user("sales", "sales_user")
        result = self.service.update_issue(
            sales,
            self.open_issue.id,
            status=Issue.Status.CLOSED,
        )
        self.assertFalse(result["updated"])
        self.open_issue.refresh_from_db()
        self.assertEqual(self.open_issue.status, Issue.Status.OPEN)

    def test_support_can_add_timeline_note(self) -> None:
        support = make_user("support", "support_user")
        result = self.service.add_update(
            support,
            self.other_issue.id,
            body="Called customer; waiting on logs.",
        )
        self.assertTrue(result["created"])
        self.assertEqual(
            IssueUpdate.objects.filter(issue=self.other_issue).count(),
            1,
        )
        update_id = result["update"]["id"]
        deleted = self.service.delete_update(support, self.other_issue.id, update_id)
        self.assertTrue(deleted["deleted"])
        self.assertEqual(
            IssueUpdate.objects.filter(issue=self.other_issue).count(),
            0,
        )

    def test_admin_can_create_issue(self) -> None:
        admin = make_user("admin", "admin")
        result = self.service.create_issue(
            admin,
            customer_id=self.customer.id,
            title="New plant access",
            description="Badge request",
            priority=Issue.Priority.HIGH,
            assigned_to="support",
        )
        self.assertTrue(result["created"])
        self.assertEqual(result["issue"]["title"], "New plant access")
        self.assertTrue(Issue.objects.filter(title="New plant access").exists())

    def test_support_cannot_create_issue(self) -> None:
        support = make_user("support", "support_user")
        result = self.service.create_issue(
            support,
            customer_id=self.customer.id,
            title="Should fail",
        )
        self.assertFalse(result["created"])

    def test_admin_can_edit_title_and_delete(self) -> None:
        admin = make_user("admin", "admin")
        updated = self.service.update_issue(
            admin,
            self.open_issue.id,
            title="Renamed shipment issue",
            description="Updated description",
        )
        self.assertTrue(updated["updated"])
        self.open_issue.refresh_from_db()
        self.assertEqual(self.open_issue.title, "Renamed shipment issue")

        deleted = self.service.delete_issue(admin, self.open_issue.id)
        self.assertTrue(deleted["deleted"])
        self.assertFalse(Issue.objects.filter(pk=self.open_issue.id).exists())

    def test_support_cannot_change_title(self) -> None:
        support = make_user("support", "support_user")
        result = self.service.update_issue(
            support,
            self.other_issue.id,
            title="Hacked title",
        )
        self.assertFalse(result["updated"])
        self.other_issue.refresh_from_db()
        self.assertEqual(self.other_issue.title, "Support-only issue")
