from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response

from core.authentication import (
    CanUpdateIssues,
    CanUseAssistant,
    IsAuthenticatedKeycloak,
    KeycloakJWTAuthentication,
)
from core.permissions import can_view_all_issues
from issues.serializers import (
    CustomerSerializer,
    IssueDetailSerializer,
    IssuePatchSerializer,
    IssueSerializer,
    IssueUpdateCreateSerializer,
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

    def patch(self, request: Request, issue_id: int) -> Response:
        if not CanUpdateIssues().has_permission(request, self):
            return Response(
                {"detail": "Only support_user or admin can update issues"},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = IssuePatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = IssueService().update_issue(
            request.user,
            issue_id,
            **serializer.validated_data,
        )
        if not result.get("updated"):
            code = (
                status.HTTP_404_NOT_FOUND
                if "not found" in str(result.get("error", "")).lower()
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({"detail": result.get("error")}, status=code)
        return Response(result)


class IssueUpdateCreateView(generics.GenericAPIView):
    """Post a timeline note on an issue (support / admin)."""

    authentication_classes = [KeycloakJWTAuthentication]
    permission_classes = [IsAuthenticatedKeycloak, CanUseAssistant, CanUpdateIssues]
    serializer_class = IssueUpdateCreateSerializer

    def post(self, request: Request, issue_id: int) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = IssueService().add_update(
            request.user,
            issue_id,
            body=serializer.validated_data["body"],
        )
        if not result.get("created"):
            code = (
                status.HTTP_404_NOT_FOUND
                if "not found" in str(result.get("error", "")).lower()
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({"detail": result.get("error")}, status=code)
        return Response(result, status=status.HTTP_201_CREATED)


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
