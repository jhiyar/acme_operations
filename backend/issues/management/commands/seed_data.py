from django.core.management.base import BaseCommand
from django.db import transaction

from issues.models import Customer, Issue, IssueUpdate, NextAction


class Command(BaseCommand):
    help = "Seed representative customers, issues, updates, and next actions"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Delete existing customers/issues and reseed",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if Customer.objects.exists() and not options["force"]:
            self.stdout.write(
                self.style.WARNING(
                    "Seed skipped — data already present (use --force to replace)"
                )
            )
            return

        if options["force"]:
            NextAction.objects.all().delete()
            IssueUpdate.objects.all().delete()
            Issue.objects.all().delete()
            Customer.objects.all().delete()

        northwind = Customer.objects.create(
            name="Northwind Traders",
            industry="Retail",
            tier="enterprise",
            account_owner="sales",
            contact_email="ops@northwind.example",
            notes=(
                "Strategic EU logistics account. Volume spikes every quarter-end. "
                "Primary contacts: Marta Ruiz (Ops), Ken Vale (Finance). "
                "Contract includes 99.5% tracking-event SLA with carrier failover credits."
            ),
        )
        contoso = Customer.objects.create(
            name="Contoso Ltd",
            industry="Manufacturing",
            tier="premium",
            account_owner="sales",
            contact_email="support@contoso.example",
            notes=(
                "Expanding into EMEA plants; highly sensitive to SLA breaches and "
                "executive visibility. Friday steering committee reviews open criticals. "
                "Plant leads escalate quickly when alert noise blocks production decisions."
            ),
        )
        fabrikam = Customer.objects.create(
            name="Fabrikam Inc",
            industry="Technology",
            tier="standard",
            account_owner="support",
            contact_email="help@fabrikam.example",
            notes=(
                "Newer logo still finishing SSO onboarding. Operations cohort blocked "
                "until IdP group mapping lands. Success criteria: all ops users can "
                "open tickets and view dashboards without shared admin accounts."
            ),
        )

        issue_nw_1 = Issue.objects.create(
            customer=northwind,
            title="Delayed shipment tracking for Client X warehouse",
            description=(
                "Northwind’s Client X warehouse (Rotterdam DC-04) stopped receiving "
                "live tracking events for outbound EU LTL shipments starting 2026-07-12 ~14:20 UTC. "
                "Symptoms: portal shows ‘label created’ then stalls; no scan events for ~38% of "
                "same-day departures. Impact: customer service cannot promise ETAs; three retail "
                "receivers threatened chargebacks. Carrier: EuroHaul Express (API v3). "
                "Temporary workaround: ops exports CSV from carrier portal twice daily, but that "
                "misses mid-route exceptions. Customer wants root cause, restored live events, "
                "and a written interim process before Monday standup."
            ),
            status=Issue.Status.OPEN,
            priority=Issue.Priority.HIGH,
            assigned_to="sales",
        )
        IssueUpdate.objects.create(
            issue=issue_nw_1,
            author="sales",
            body=(
                "Marta Ruiz asked for a firm ETA on restoring live tracking events and "
                "whether chargeback risk is covered under the SLA credit clause. She also "
                "requested a shared sheet of delayed POs for Client X buyers."
            ),
        )
        IssueUpdate.objects.create(
            issue=issue_nw_1,
            author="support",
            body=(
                "EuroHaul API /v3/events intermittent 502/504 between 13:50–17:10 UTC. "
                "Opened vendor ticket #44821. Webhook retries succeed after ~4–11 minutes, "
                "which explains portal gaps. Staging replay of 12 Jul traffic reproduced "
                "missing ‘departed_origin’ events when payload size > 256KB."
            ),
        )
        IssueUpdate.objects.create(
            issue=issue_nw_1,
            author="support",
            body=(
                "Vendor acknowledged a throttle bug on multi-stop LTL batches. Patch ETA "
                "is 2026-07-18 EOD. We proposed interim: poll /v3/events every 15m for "
                "Northwind account codes NL-NW-* and push synthetic updates into our bus."
            ),
        )
        NextAction.objects.create(
            issue=issue_nw_1,
            summary=(
                "Schedule EuroHaul bridge call with Northwind ops and share interim "
                "manual tracking sheet for Client X POs until patch lands."
            ),
            recommended_by="support",
        )

        issue_nw_2 = Issue.objects.create(
            customer=northwind,
            title="Invoice mismatch on March retainer",
            description=(
                "March retainer invoice INV-2026-0317 billed 1,240 ‘active lane’ units at "
                "the enterprise rate, but contracted volume for Q1 was capped at 1,050 with "
                "overage at a lower tier-2 rate. Finance delta is ~€18.4k. Northwind disputes "
                "the dual rate-card application and wants a corrected credit memo plus "
                "confirmation that April will use the amended schedule attached to Amendment B."
            ),
            status=Issue.Status.IN_PROGRESS,
            priority=Issue.Priority.MEDIUM,
            assigned_to="sales",
        )
        IssueUpdate.objects.create(
            issue=issue_nw_2,
            author="sales",
            body=(
                "Finance confirmed dual rate cards were applied incorrectly after the "
                "February SKU migration. Draft credit memo CRM-8841 prepared for €18,420."
            ),
        )
        IssueUpdate.objects.create(
            issue=issue_nw_2,
            author="admin",
            body=(
                "Legal reviewed Amendment B: tier-2 overage applies only after 1,050 units. "
                "Waiting on Ken Vale to accept credit memo language before we reissue April."
            ),
        )

        issue_ct_1 = Issue.objects.create(
            customer=contoso,
            title="Production line alert noise after firmware update",
            description=(
                "After Contoso Plant 3 applied edge firmware 4.8.2 on 2026-07-10, operators "
                "receive 200–400 false-positive ‘vibration anomaly’ alerts per shift on lines "
                "B2 and B3. Real faults are buried; two near-miss stoppages occurred when "
                "staff muted the stream. Previous baseline (firmware 4.7.9) used hysteresis "
                "window 90s / threshold 0.42g. Current build appears to use 15s / 0.28g with "
                "no plant-specific profile. Customer needs: (1) quiet staging validation, "
                "(2) rollback or tuned profile for Plant 3 before Friday steering committee, "
                "(3) executive-ready summary of risk and timeline."
            ),
            status=Issue.Status.OPEN,
            priority=Issue.Priority.CRITICAL,
            assigned_to="support",
        )
        IssueUpdate.objects.create(
            issue=issue_ct_1,
            author="support",
            body=(
                "Rolled alert threshold to previous baseline (0.42g, 90s hysteresis) in "
                "staging for Plant 3 twin. Alert volume dropped ~92% on replay of 48h logs. "
                "Still validating that genuine spindle faults from June still fire."
            ),
        )
        IssueUpdate.objects.create(
            issue=issue_ct_1,
            author="admin",
            body=(
                "Contoso asked for an executive summary before Friday steering committee: "
                "root cause hypothesis, mitigation already applied in staging, production "
                "cutover window, and residual risk if we delay past Monday."
            ),
        )
        IssueUpdate.objects.create(
            issue=issue_ct_1,
            author="support",
            body=(
                "Firmware vendor confirmed default profile change in 4.8.2 release notes "
                "(missed in our upgrade checklist). Proposed path: ship plant profile "
                "override via config push (no firmware rollback) Sunday 02:00–04:00 local."
            ),
        )

        issue_ct_2 = Issue.objects.create(
            customer=contoso,
            title="Access request for new plant supervisors",
            description=(
                "Four new Plant 2 supervisors need read-only dashboard access to OEE, "
                "downtime, and quality tiles. Names provided to Contoso IT on 2026-06-28. "
                "No elevated write permissions. Access should use Contoso Azure AD groups "
                "ops-plant2-supervisors once SSO mapping is confirmed."
            ),
            status=Issue.Status.RESOLVED,
            priority=Issue.Priority.LOW,
            assigned_to="support",
        )
        IssueUpdate.objects.create(
            issue=issue_ct_2,
            author="support",
            body=(
                "Accounts provisioned into read-only role and confirmed by Contoso IT. "
                "Users verified login on 2026-07-02. Ticket closed."
            ),
        )

        issue_fb_1 = Issue.objects.create(
            customer=fabrikam,
            title="Onboarding checklist incomplete — SSO mapping",
            description=(
                "Fabrikam IdP (Okta) group ‘ops-operators’ is not mapped to our "
                "operations-user role. Without mapping, 17 operators cannot create tickets "
                "or view their queue; they currently share a break-glass admin which violates "
                "Fabrikam security policy. Blockers: waiting on updated SAML metadata "
                "(entityID change) and confirmation of nested group ‘ops-operators-emea’. "
                "Target go-live was 2026-07-15; slipped once already."
            ),
            status=Issue.Status.OPEN,
            priority=Issue.Priority.HIGH,
            assigned_to="admin",
        )
        IssueUpdate.objects.create(
            issue=issue_fb_1,
            author="admin",
            body=(
                "Waiting on Fabrikam IdP metadata refresh. Their IAM lead said XML would "
                "arrive by 2026-07-16 COB; not received as of 2026-07-17 morning."
            ),
        )
        IssueUpdate.objects.create(
            issue=issue_fb_1,
            author="support",
            body=(
                "Prepared role-mapping config for ops-operators → operations-user and "
                "ops-operators-emea → operations-user. Ready to apply within 30 minutes "
                "of metadata validation."
            ),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {Customer.objects.count()} customers, "
                f"{Issue.objects.count()} issues, "
                f"{IssueUpdate.objects.count()} updates, "
                f"{NextAction.objects.count()} next actions"
            )
        )
