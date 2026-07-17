from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from issues.models import Customer


class CustomerService:
    def get_by_name(self, customer_name: str) -> Customer | None:
        return Customer.objects.filter(name__iexact=customer_name.strip()).first()

    def list_all(self) -> QuerySet[Customer]:
        return Customer.objects.all()

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
