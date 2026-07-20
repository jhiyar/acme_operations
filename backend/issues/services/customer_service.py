from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from core.services.keycloak_auth_service import KeycloakUser
from issues.models import Customer
from issues.permissions import can_manage_customers


class CustomerService:
    def get_by_name(self, customer_name: str) -> Customer | None:
        name = customer_name.strip()
        if not name:
            return None
        exact = Customer.objects.filter(name__iexact=name).first()
        if exact:
            return exact
        matches = list(Customer.objects.filter(name__icontains=name).order_by("name")[:5])
        if len(matches) == 1:
            return matches[0]
        return None

    def find_matches(self, customer_name: str, *, limit: int = 5) -> list[Customer]:
        name = customer_name.strip()
        if not name:
            return []
        exact = list(Customer.objects.filter(name__iexact=name)[:1])
        if exact:
            return exact
        return list(
            Customer.objects.filter(name__icontains=name).order_by("name")[:limit]
        )

    def list_all(self) -> QuerySet[Customer]:
        return Customer.objects.all()

    def get_by_id(self, customer_id: int) -> Customer | None:
        return Customer.objects.filter(pk=customer_id).first()

    def create_customer(
        self,
        user: KeycloakUser,
        *,
        name: str,
        industry: str = "",
        tier: str = "standard",
        account_owner: str = "",
        contact_email: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        if not can_manage_customers(user):
            return {
                "created": False,
                "error": "Only admin can create customers",
                "code": "forbidden",
            }

        cleaned_name = name.strip()
        if not cleaned_name:
            return {
                "created": False,
                "error": "Name is required",
                "code": "bad_request",
            }

        if Customer.objects.filter(name__iexact=cleaned_name).exists():
            return {
                "created": False,
                "error": f"Customer “{cleaned_name}” already exists",
                "code": "bad_request",
            }

        customer = Customer.objects.create(
            name=cleaned_name,
            industry=(industry or "").strip(),
            tier=(tier or "standard").strip() or "standard",
            account_owner=(account_owner or "").strip(),
            contact_email=(contact_email or "").strip(),
            notes=(notes or "").strip(),
        )
        return {"created": True, "customer": self.to_dict(customer)}

    def update_customer(
        self,
        user: KeycloakUser,
        customer_id: int,
        *,
        name: str | None = None,
        industry: str | None = None,
        tier: str | None = None,
        account_owner: str | None = None,
        contact_email: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        if not can_manage_customers(user):
            return {
                "updated": False,
                "error": "Only admin can update customers",
                "code": "forbidden",
            }

        customer = self.get_by_id(customer_id)
        if not customer:
            return {
                "updated": False,
                "error": f"Customer #{customer_id} not found",
                "code": "not_found",
            }

        fields: list[str] = []
        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                return {
                    "updated": False,
                    "error": "Name is required",
                    "code": "bad_request",
                }
            clash = (
                Customer.objects.filter(name__iexact=cleaned)
                .exclude(pk=customer.id)
                .exists()
            )
            if clash:
                return {
                    "updated": False,
                    "error": f"Customer “{cleaned}” already exists",
                    "code": "bad_request",
                }
            customer.name = cleaned
            fields.append("name")
        if industry is not None:
            customer.industry = industry.strip()
            fields.append("industry")
        if tier is not None:
            cleaned_tier = tier.strip() or "standard"
            customer.tier = cleaned_tier
            fields.append("tier")
        if account_owner is not None:
            customer.account_owner = account_owner.strip()
            fields.append("account_owner")
        if contact_email is not None:
            customer.contact_email = contact_email.strip()
            fields.append("contact_email")
        if notes is not None:
            customer.notes = notes.strip()
            fields.append("notes")

        if not fields:
            return {
                "updated": False,
                "error": "No updatable fields provided",
                "code": "bad_request",
            }

        fields.append("updated_at")
        customer.save(update_fields=fields)
        return {"updated": True, "customer": self.to_dict(customer)}

    def delete_customer(self, user: KeycloakUser, customer_id: int) -> dict[str, Any]:
        if not can_manage_customers(user):
            return {
                "deleted": False,
                "error": "Only admin can delete customers",
                "code": "forbidden",
            }

        customer = self.get_by_id(customer_id)
        if not customer:
            return {
                "deleted": False,
                "error": f"Customer #{customer_id} not found",
                "code": "not_found",
            }

        issue_count = customer.issues.count()
        if issue_count:
            return {
                "deleted": False,
                "error": (
                    f"Customer has {issue_count} issue(s). "
                    "Delete or reassign them before removing the customer."
                ),
                "code": "bad_request",
            }

        customer.delete()
        return {"deleted": True, "id": customer_id}

    def to_dict(self, customer: Customer) -> dict[str, Any]:
        return {
            "id": customer.id,
            "name": customer.name,
            "industry": customer.industry,
            "tier": customer.tier,
            "account_owner": customer.account_owner,
            "contact_email": customer.contact_email,
            "notes": customer.notes,
        }
