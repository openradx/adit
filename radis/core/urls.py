from django.urls import path

from .views import (
    BroadcastView,
    FlowerProxyView,
    HomeView,
    UpdatePreferencesView,
    admin_section,
)

urlpatterns = [
    path(
        "update-preferences/",
        UpdatePreferencesView.as_view(),
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
]
