from django.urls import path

from .views import SandboxListView, sandbox_messages

urlpatterns = [
    path(
        "",
        SandboxListView.as_view(),
        name="sandbox_list",
    ),
    path(
        "messages/",
        sandbox_messages,
        name="sandbox_messages",
    ),
]
