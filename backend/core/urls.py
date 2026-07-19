from django.urls import include, path

from core.views import (
    AgentToolCallView,
    AgentToolsView,
    ChatView,
    ConversationDetailView,
    ConversationListCreateView,
    HealthView,
    MeView,
)

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("me/", MeView.as_view(), name="me"),
    path("chat/", ChatView.as_view(), name="chat"),
    path(
        "conversations/",
        ConversationListCreateView.as_view(),
        name="conversations",
    ),
    path(
        "conversations/<uuid:conversation_id>/",
        ConversationDetailView.as_view(),
        name="conversation-detail",
    ),
    path("agent/tools/", AgentToolsView.as_view(), name="agent-tools"),
    path("agent/tools/call/", AgentToolCallView.as_view(), name="agent-tool-call"),
    path("", include("issues.urls")),
]
