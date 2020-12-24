from django.urls import path
from django.views.generic import TemplateView
from .views import FlowerProxyView

urlpatterns = [
    path(
        "admin-section/",
        TemplateView.as_view(template_name="core/admin_section.html"),
        name="admin_section",
    ),
    path("", TemplateView.as_view(template_name="core/home.html"), name="home"),
    FlowerProxyView.as_url(),
]
