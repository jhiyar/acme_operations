from django.urls import include, path

from core.views import (
    AgentRunDetailView,
    AgentRunListView,
    AgentToolCallView,
    AgentToolsView,
    HealthView,
    MeView,
    UserDetailView,
    UserListCreateView,
)

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("me/", MeView.as_view(), name="me"),
    path("", include("chat.urls")),
    path("users/", UserListCreateView.as_view(), name="users"),
    path("users/<str:user_id>/", UserDetailView.as_view(), name="user-detail"),
    path("admin/runs/", AgentRunListView.as_view(), name="admin-runs"),
    path(
        "admin/runs/<uuid:run_id>/",
        AgentRunDetailView.as_view(),
        name="admin-run-detail",
    ),
    path("agent/tools/", AgentToolsView.as_view(), name="agent-tools"),
    path("agent/tools/call/", AgentToolCallView.as_view(), name="agent-tool-call"),
    path("", include("issues.urls")),
]
