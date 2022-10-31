from django.urls import path
from .views import (
    sandbox,
    admin_section,
    BroadcastView,
    HomeView,
    RabbitManagementProxyView,
    FlowerProxyView,
    Orthanc1ProxyView,
    Orthanc2ProxyView,
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
    Orthanc1ProxyView.as_url(),
    Orthanc2ProxyView.as_url(),
]
