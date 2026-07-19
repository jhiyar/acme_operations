from django.urls import path

from issues.views import (
    CustomerListView,
    IssueDetailView,
    IssueListView,
    IssueUpdateCreateView,
)

urlpatterns = [
    path("issues/", IssueListView.as_view(), name="issues"),
    path("issues/<int:issue_id>/", IssueDetailView.as_view(), name="issue-detail"),
    path(
        "issues/<int:issue_id>/updates/",
        IssueUpdateCreateView.as_view(),
        name="issue-updates",
    ),
    path("customers/", CustomerListView.as_view(), name="customers"),
]
