from django.urls import path
from django.views.generic import TemplateView
from .views import FlowerProxyView

urlpatterns = [
    path("", TemplateView.as_view(template_name="core/home.html"), name="home"),
    FlowerProxyView.as_url(),
]
