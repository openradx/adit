from django.urls import path

from .views import DeleteTokenView, GenerateTokenView, ListTokenView, TestView, TokenDashboardView

urlpatterns = [
    path(
        "",
        TokenDashboardView.as_view(),
        name="token_authentication",
    ),
    path(
        "generate_token",
        GenerateTokenView.as_view(),
        name="token_authentication_generate_token",
    ),
    path(
        "delete_token",
        DeleteTokenView.as_view(),
        name="token_authentication_delete_token",
    ),
    path(
        "_token_list",
        ListTokenView.as_view(),
        name="token_authentication_token_list",
    ),
    path("test", TestView.as_view(), name="test_view"),
]
