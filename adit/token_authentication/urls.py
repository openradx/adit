from django.urls import path

from .views import DeleteTokenView, TestView, TokenDashboardView

urlpatterns = [
    path(
        "",
        TokenDashboardView.as_view(),
        name="token_dashboard",
    ),
    path(
        "<int:pk>/delete-token",
        DeleteTokenView.as_view(),
        name="delete_token",
    ),
    path("test", TestView.as_view(), name="test_view"),
]
