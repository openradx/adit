from adit_radis_shared.common.views import BroadcastView
from django.urls import path

from .views import (
    HomeView,
    Orthanc1ProxyView,
    Orthanc2ProxyView,
    UpdatePreferencesView,
    admin_section,
    health,
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
    path(
        "health/",
        health,
        name="health",
    ),
    Orthanc1ProxyView.as_url(),
    Orthanc2ProxyView.as_url(),
]
