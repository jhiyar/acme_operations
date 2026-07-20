from __future__ import annotations

from rest_framework import status
from rest_framework.test import APITestCase

from core.services.keycloak_auth_service import KeycloakUser
from issues.models import Customer, Issue


def make_user(username: str, *roles: str) -> KeycloakUser:
    return KeycloakUser(
        sub=f"sub-{username}",
        username=username,
        email=f"{username}@example.com",
        roles=list(roles),
    )


class IssueApiRbacTests(APITestCase):
    def setUp(self) -> None:
        self.customer = Customer.objects.create(name="Contoso Ltd")
        self.assigned = Issue.objects.create(
            customer=self.customer,
            title="Assigned to support",
            description="Printer offline",
            status=Issue.Status.OPEN,
            priority=Issue.Priority.MEDIUM,
            assigned_to="support",
        )
        self.other = Issue.objects.create(
            customer=self.customer,
            title="Assigned to sales",
            description="Quote follow-up",
            status=Issue.Status.OPEN,
            priority=Issue.Priority.LOW,
            assigned_to="sales",
        )
        self.admin = make_user("admin", "admin")
        self.support = make_user("support", "support_user")
        self.sales = make_user("sales", "sales_user")

    def test_sales_sees_only_assigned(self) -> None:
        self.client.force_authenticate(user=self.sales)
        response = self.client.get("/api/issues/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["scope"], "assigned")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["issues"][0]["id"], self.other.id)

    def test_admin_sees_all_and_can_create(self) -> None:
        self.client.force_authenticate(user=self.admin)
        listed = self.client.get("/api/issues/")
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(listed.data["scope"], "all")
        self.assertEqual(listed.data["count"], 2)

        created = self.client.post(
            "/api/issues/",
            {
                "customer_id": self.customer.id,
                "title": "New admin issue",
                "description": "Badge request",
                "assigned_to": "support",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertTrue(created.data["created"])
        self.assertEqual(created.data["issue"]["title"], "New admin issue")

    def test_support_cannot_create_or_delete(self) -> None:
        self.client.force_authenticate(user=self.support)
        created = self.client.post(
            "/api/issues/",
            {
                "customer_id": self.customer.id,
                "title": "Should fail",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_403_FORBIDDEN)

        deleted = self.client.delete(f"/api/issues/{self.assigned.id}/")
        self.assertEqual(deleted.status_code, status.HTTP_403_FORBIDDEN)

    def test_support_can_patch_status_and_post_note(self) -> None:
        self.client.force_authenticate(user=self.support)
        patched = self.client.patch(
            f"/api/issues/{self.assigned.id}/",
            {"status": "in_progress"},
            format="json",
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertTrue(patched.data["updated"])

        note = self.client.post(
            f"/api/issues/{self.assigned.id}/updates/",
            {"body": "Called customer"},
            format="json",
        )
        self.assertEqual(note.status_code, status.HTTP_201_CREATED)
        self.assertTrue(note.data["created"])

    def test_support_cannot_change_title(self) -> None:
        self.client.force_authenticate(user=self.support)
        patched = self.client.patch(
            f"/api/issues/{self.assigned.id}/",
            {"title": "Hacked"},
            format="json",
        )
        self.assertEqual(patched.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_delete(self) -> None:
        self.client.force_authenticate(user=self.admin)
        deleted = self.client.delete(f"/api/issues/{self.other.id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Issue.objects.filter(pk=self.other.id).exists())

    def test_unauthenticated_rejected(self) -> None:
        response = self.client.get("/api/issues/")
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


class CustomerApiRbacTests(APITestCase):
    def setUp(self) -> None:
        self.customer = Customer.objects.create(name="Fabrikam")
        self.admin = make_user("admin", "admin")
        self.support = make_user("support", "support_user")

    def test_assistant_can_list(self) -> None:
        self.client.force_authenticate(user=self.support)
        response = self.client.get("/api/customers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_support_cannot_create(self) -> None:
        self.client.force_authenticate(user=self.support)
        response = self.client.post(
            "/api/customers/",
            {"name": "Blocked"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_crud(self) -> None:
        self.client.force_authenticate(user=self.admin)
        created = self.client.post(
            "/api/customers/",
            {
                "name": "Adventure Works",
                "industry": "Retail",
                "tier": "premium",
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        customer_id = created.data["customer"]["id"]

        patched = self.client.patch(
            f"/api/customers/{customer_id}/",
            {"notes": "Strategic account"},
            format="json",
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(patched.data["customer"]["notes"], "Strategic account")

        deleted = self.client.delete(f"/api/customers/{customer_id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
