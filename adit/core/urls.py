from django.urls import path
from .views import admin_section, HomeView, FlowerProxyView

urlpatterns = [
    path(
        "admin-section/",
        admin_section,
        name="admin_section",
    ),
    path("", HomeView.as_view(), name="home"),
    FlowerProxyView.as_url(),
]
