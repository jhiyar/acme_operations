from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response

from core.authentication import KeycloakJWTAuthentication
from core.permissions import CanUseAssistant, IsAuthenticatedKeycloak
from issues.permissions import (
    CanManageIssues,
    CanUpdateIssues,
    can_view_all_issues,
)
from issues.serializers import (
    CustomerSerializer,
    IssueDetailSerializer,
    IssuePatchSerializer,
    IssueSerializer,
    IssueUpdateCreateSerializer,
    IssueWriteSerializer,
)
from issues.services import CustomerService, IssueService


def _service_error_status(result: dict) -> int:
    code = result.get("code")
    if code == "not_found":
        return status.HTTP_404_NOT_FOUND
    if code == "forbidden":
        return status.HTTP_403_FORBIDDEN
    if "not found" in str(result.get("error", "")).lower():
        return status.HTTP_404_NOT_FOUND
    return status.HTTP_400_BAD_REQUEST


class IssueListCreateView(generics.ListCreateAPIView):
    """List visible issues; admin may create via POST."""

    authentication_classes = [KeycloakJWTAuthentication]
    serializer_class = IssueSerializer

    def get_permissions(self):
        permissions = [IsAuthenticatedKeycloak(), CanUseAssistant()]
        if self.request.method == "POST":
            permissions.append(CanManageIssues())
        return permissions

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

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = IssueWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = IssueService().create_issue(request.user, **serializer.validated_data)
        if not result.get("created"):
            return Response(
                {"detail": result.get("error")},
                status=_service_error_status(result),
            )
        return Response(result, status=status.HTTP_201_CREATED)


class IssueDetailView(generics.RetrieveAPIView):
    """Retrieve / patch / delete a single issue (RBAC differs by method)."""

    authentication_classes = [KeycloakJWTAuthentication]
    serializer_class = IssueDetailSerializer
    lookup_url_kwarg = "issue_id"

    def get_permissions(self):
        permissions = [IsAuthenticatedKeycloak(), CanUseAssistant()]
        if self.request.method == "PATCH":
            permissions.append(CanUpdateIssues())
        elif self.request.method == "DELETE":
            permissions.append(CanManageIssues())
        return permissions

    def get_queryset(self):
        return IssueService().visible_to(self.request.user)

    def patch(self, request: Request, issue_id: int) -> Response:
        serializer = IssuePatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = IssueService().update_issue(
            request.user,
            issue_id,
            **serializer.validated_data,
        )
        if not result.get("updated"):
            return Response(
                {"detail": result.get("error")},
                status=_service_error_status(result),
            )
        return Response(result)

    def delete(self, request: Request, issue_id: int) -> Response:
        result = IssueService().delete_issue(request.user, issue_id)
        if not result.get("deleted"):
            return Response(
                {"detail": result.get("error")},
                status=_service_error_status(result),
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


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
            return Response(
                {"detail": result.get("error")},
                status=_service_error_status(result),
            )
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
