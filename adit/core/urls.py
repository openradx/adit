from django.urls import path
from django.views.generic import TemplateView
from .views import admin_section, FlowerProxyView

urlpatterns = [
    path(
        "admin-section/",
        admin_section,
        name="admin_section",
    ),
    path("", TemplateView.as_view(template_name="core/home.html"), name="home"),
    FlowerProxyView.as_url(),
]
