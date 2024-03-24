from django.urls import path

from adit_radis_shared.common.views import HtmxTemplateView

from .views import DeleteTokenView, TestView, TokenDashboardView

urlpatterns = [
    path(
        "",
        TokenDashboardView.as_view(),
        name="token_dashboard",
    ),
    path(
        "help/",
        HtmxTemplateView.as_view(
            template_name="token_authentication/_token_authentication_help.html"
        ),
        name="token_authentication_help",
    ),
    path(
        "<int:pk>/delete-token",
        DeleteTokenView.as_view(),
        name="delete_token",
    ),
    path("test", TestView.as_view(), name="test_view"),
]
