from django.urls import path

from issues.views import (
    CustomerDetailView,
    CustomerListCreateView,
    IssueDetailView,
    IssueListCreateView,
    IssueUpdateCreateView,
)

urlpatterns = [
    path("issues/", IssueListCreateView.as_view(), name="issues"),
    path("issues/<int:issue_id>/", IssueDetailView.as_view(), name="issue-detail"),
    path(
        "issues/<int:issue_id>/updates/",
        IssueUpdateCreateView.as_view(),
        name="issue-updates",
    ),
    path("customers/", CustomerListCreateView.as_view(), name="customers"),
    path(
        "customers/<int:customer_id>/",
        CustomerDetailView.as_view(),
        name="customer-detail",
    ),
]
