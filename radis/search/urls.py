from django.urls import path

from .views import PreviewView, SearchView

urlpatterns = [
    path("", SearchView.as_view(), name="search"),
    path("preview/<str:doc_id>/", PreviewView.as_view(), name="preview"),
]
