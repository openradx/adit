from django.urls import path

from .views import AsyncSandboxClassView, SandboxListView, sandbox_messages

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
    path(
        "async-class-view/",
        AsyncSandboxClassView.as_view(),
        name="sandbox_async_class_view",
    ),
]
