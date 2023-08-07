from django.urls import path

from .views import (
    BroadcastView,
    FlowerProxyView,
    HomeView,
    Orthanc1ProxyView,
    Orthanc2ProxyView,
    RabbitManagementProxyView,
    UpdatePreferencesView,
    admin_section,
    sandbox,
)

urlpatterns = [
    path(
        "update-preferences/",
        UpdatePreferencesView.as_view(),
    ),
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
    Orthanc1ProxyView.as_url(),
    Orthanc2ProxyView.as_url(),
]
