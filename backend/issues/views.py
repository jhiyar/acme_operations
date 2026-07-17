from rest_framework import generics
from rest_framework.request import Request
from rest_framework.response import Response

from core.authentication import (
    CanUseAssistant,
    IsAuthenticatedKeycloak,
    KeycloakJWTAuthentication,
)
from core.permissions import can_view_all_issues
from issues.serializers import (
    CustomerSerializer,
    IssueDetailSerializer,
    IssueSerializer,
)
from issues.services import CustomerService, IssueService


class IssueListView(generics.ListAPIView):
    """Admin sees all issues; other roles see only issues assigned to them."""

    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [IsAuthenticatedKeycloak, CanUseAssistant]
    serializer_class = IssueSerializer

    def get_queryset(self):
        qs = IssueService().visible_to(self.request.user)
        status_filter = self.request.query_params.get("status")
        customer_name = self.request.query_params.get("customer")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if customer_name:
            qs = qs.filter(customer__name__iexact=customer_name.strip())
        return qs

    def list(self, request: Request, *args, **kwargs) -> Response:
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "scope": "all" if can_view_all_issues(request.user) else "assigned",
                "count": len(serializer.data),
                "issues": serializer.data,
            }
        )


class IssueDetailView(generics.RetrieveAPIView):
    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [IsAuthenticatedKeycloak, CanUseAssistant]
    serializer_class = IssueDetailSerializer
    lookup_url_kwarg = "issue_id"

    def get_queryset(self):
        return IssueService().visible_to(self.request.user)


class CustomerListView(generics.ListAPIView):
    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [IsAuthenticatedKeycloak, CanUseAssistant]
    serializer_class = CustomerSerializer

    def get_queryset(self):
        return CustomerService().list_all()

    def list(self, request: Request, *args, **kwargs) -> Response:
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response({"count": len(serializer.data), "customers": serializer.data})
