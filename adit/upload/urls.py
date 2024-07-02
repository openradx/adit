from django.urls import path

from .views import UploadCreateView, UploadUpdatePreferencesView, uploadAPIView

urlpatterns = [
    path(
        "update-preferences/",
        UploadUpdatePreferencesView.as_view(),
    ),
    path(
        "jobs/new",
        UploadCreateView.as_view(),
        name="upload_job_create",
    ),
    path("data-upload/<str:node_id>/", view=uploadAPIView, name="data_upload"),
]
