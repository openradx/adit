from django.urls import path

from .views import (
    BroadcastView,
    FlowerProxyView,
    HomeView,
    RabbitManagementProxyView,
    admin_section,
    sandbox,
)

urlpatterns = [
    path(
        "sandbox/",
        sandbox,
        name="sandbox",
    ),
    path(
        "admin-section/",
        admin_section,
        name="admin_section",
    ),
    path(
        "admin-section/broadcast/",
        BroadcastView.as_view(),
        name="broadcast",
    ),
    path(
        "",
        HomeView.as_view(),
        name="home",
    ),
    RabbitManagementProxyView.as_url(),
    FlowerProxyView.as_url(),
]
