from django.urls import path

from .views import DeleteTokenView, GenerateTokenView, TestView, TokenDashboardView

urlpatterns = [
    path(
        "",
        TokenDashboardView.as_view(),
        name="token_dashboard",
    ),
    path(
        "generate-token",
        GenerateTokenView.as_view(),
        name="generate_token",
    ),
    path(
        "delete-token",
        DeleteTokenView.as_view(),
        name="delete_token",
    ),
    path("test", TestView.as_view(), name="test_view"),
]
