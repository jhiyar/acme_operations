from django.urls import path

from issues.views import CustomerListView, IssueDetailView, IssueListView

urlpatterns = [
    path("issues/", IssueListView.as_view(), name="issues"),
    path("issues/<int:issue_id>/", IssueDetailView.as_view(), name="issue-detail"),
    path("customers/", CustomerListView.as_view(), name="customers"),
]
