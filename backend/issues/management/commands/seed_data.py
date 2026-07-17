from django.core.management.base import BaseCommand
from django.db import transaction

from issues.models import Customer, Issue, IssueUpdate, NextAction


class Command(BaseCommand):
    help = "Seed representative customers, issues, updates, and next actions"

    @transaction.atomic
    def handle(self, *args, **options):
        if Customer.objects.exists():
            self.stdout.write(self.style.WARNING("Seed skipped — data already present"))
            return

        northwind = Customer.objects.create(
            name="Northwind Traders",
            industry="Retail",
            tier="enterprise",
            account_owner="sales",
            contact_email="ops@northwind.example",
            notes="Strategic account with recurring logistics escalations.",
        )
        contoso = Customer.objects.create(
            name="Contoso Ltd",
            industry="Manufacturing",
            tier="premium",
            account_owner="sales",
            contact_email="support@contoso.example",
            notes="Expanding into EMEA; sensitive to SLA breaches.",
        )
        fabrikam = Customer.objects.create(
            name="Fabrikam Inc",
            industry="Technology",
            tier="standard",
            account_owner="support",
            contact_email="help@fabrikam.example",
            notes="Newer logo; onboarding still in progress.",
        )

        issue_nw_1 = Issue.objects.create(
            customer=northwind,
            title="Delayed shipment tracking for Client X warehouse",
            description="Customer reports tracking gaps on outbound EU shipments.",
            status=Issue.Status.OPEN,
            priority=Issue.Priority.HIGH,
            assigned_to="sales",
        )
        IssueUpdate.objects.create(
            issue=issue_nw_1,
            author="sales",
            body="Customer asked for ETA on restoring live tracking events.",
        )
        IssueUpdate.objects.create(
            issue=issue_nw_1,
            author="support",
            body="Carrier API intermittent; opened vendor ticket #44821.",
        )
        NextAction.objects.create(
            issue=issue_nw_1,
            summary="Schedule carrier bridge call and share interim manual tracking sheet.",
            recommended_by="support",
        )

        issue_nw_2 = Issue.objects.create(
            customer=northwind,
            title="Invoice mismatch on March retainer",
            description="Billing line items do not match contracted volumes.",
            status=Issue.Status.IN_PROGRESS,
            priority=Issue.Priority.MEDIUM,
            assigned_to="sales",
        )
        IssueUpdate.objects.create(
            issue=issue_nw_2,
            author="sales",
            body="Finance confirmed dual rate cards were applied incorrectly.",
        )

        issue_ct_1 = Issue.objects.create(
            customer=contoso,
            title="Production line alert noise after firmware update",
            description="Operators flooded with false-positive machine alerts.",
            status=Issue.Status.OPEN,
            priority=Issue.Priority.CRITICAL,
            assigned_to="support",
        )
        IssueUpdate.objects.create(
            issue=issue_ct_1,
            author="support",
            body="Rolled alert threshold to previous baseline in staging.",
        )
        IssueUpdate.objects.create(
            issue=issue_ct_1,
            author="admin",
            body="Customer asked for executive summary before Friday steering committee.",
        )

        issue_ct_2 = Issue.objects.create(
            customer=contoso,
            title="Access request for new plant supervisors",
            description="Four supervisors need read-only dashboard access.",
            status=Issue.Status.RESOLVED,
            priority=Issue.Priority.LOW,
            assigned_to="support",
        )
        IssueUpdate.objects.create(
            issue=issue_ct_2,
            author="support",
            body="Accounts provisioned and confirmed by Contoso IT.",
        )

        issue_fb_1 = Issue.objects.create(
            customer=fabrikam,
            title="Onboarding checklist incomplete — SSO mapping",
            description="IdP group mapping still missing for operations cohort.",
            status=Issue.Status.OPEN,
            priority=Issue.Priority.HIGH,
            assigned_to="admin",
        )
        IssueUpdate.objects.create(
            issue=issue_fb_1,
            author="admin",
            body="Waiting on Fabrikam IdP metadata refresh.",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {Customer.objects.count()} customers, "
                f"{Issue.objects.count()} issues, "
                f"{IssueUpdate.objects.count()} updates, "
                f"{NextAction.objects.count()} next actions"
            )
        )
