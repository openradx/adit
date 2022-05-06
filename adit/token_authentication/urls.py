from django.urls import path
from .views import (
    RestAuthView,
    RestAuthGenerateTokenView,
    RestAuthDeleteTokenView,
    RestAuthTokenListView,
)
from rest_framework.authtoken.views import ObtainAuthToken


urlpatterns = [
    path(
        "token_authentication",
        RestAuthView.as_view(),
        name="token_authentication",
    ),
    path(
        "token_authentication/generate_token",
        RestAuthGenerateTokenView.as_view(),
        name="token_authentication_generate_token"
    ),
    path(
        "token_authentication/delete_token",
        RestAuthDeleteTokenView.as_view(),
        name="token_authentication_delete_token"
    ),
    path(
        "token_authentication/_token_list",
        RestAuthTokenListView.as_view(),
        name="token_authentication_token_list",
    ),
]
