from __future__ import annotations

from typing import Any

from django.db.models import QuerySet

from issues.models import Customer


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
