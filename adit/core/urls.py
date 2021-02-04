from django.urls import path
from .views import sandbox, admin_section, HomeView, FlowerProxyView

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
        "",
        HomeView.as_view(),
        name="home",
    ),
    FlowerProxyView.as_url(),
]
