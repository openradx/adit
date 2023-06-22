from django.urls import path
from rest_framework.authtoken.views import ObtainAuthToken

from .views import (
    DeleteTokenView,
    GenerateTokenView,
    ListTokenView,
    TokenDashboardView,
)

urlpatterns = [
    path(
        "token_authentication",
        TokenDashboardView.as_view(),
        name="token_authentication",
    ),
    path(
        "token_authentication/generate_token",
        GenerateTokenView.as_view(),
        name="token_authentication_generate_token",
    ),
    path(
        "token_authentication/delete_token",
        DeleteTokenView.as_view(),
        name="token_authentication_delete_token",
    ),
    path(
        "token_authentication/_token_list",
        ListTokenView.as_view(),
        name="token_authentication_token_list",
    ),
]
