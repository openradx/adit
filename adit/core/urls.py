from django.urls import path
from .views import (
    sandbox,
    admin_section,
    BroadcastView,
    HomeView,
    FlowerProxyView,
    RabbitManagementProxyView,
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
    FlowerProxyView.as_url(),
    RabbitManagementProxyView.as_url(),
]
