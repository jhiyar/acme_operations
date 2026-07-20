from django.urls import path

from chat.views import ChatView, ConversationDetailView, ConversationListCreateView

urlpatterns = [
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
]
