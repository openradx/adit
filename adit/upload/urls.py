from django.urls import path

from .views import UploadCreateView, UploadUpdatePreferencesView, upload_api_view

urlpatterns = [
    path(
        "update-preferences/",
        UploadUpdatePreferencesView.as_view(),
    ),
    path(
        "jobs/new/",
        UploadCreateView.as_view(),
        name="upload_create",
    ),
    path("data-upload/<str:node_id>/", view=upload_api_view, name="data_upload"),
]
