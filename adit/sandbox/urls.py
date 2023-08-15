from django.urls import path

from .views import AsyncSandboxClassView, SandboxListView, sandbox_messages, sandbox_toasts

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
        "toasts/",
        sandbox_toasts,
        name="sandbox_toasts",
    ),
    path(
        "async-class-view/",
        AsyncSandboxClassView.as_view(),
        name="sandbox_async_class_view",
    ),
]
