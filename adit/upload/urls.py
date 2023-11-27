from django.urls import path

from .views import UploadAPIView, UploadJobCreateView, UploadUpdatePreferencesView

urlpatterns = [
    path(
        "update-preferences/",
        UploadUpdatePreferencesView.as_view(),
    ),
    path(
        "jobs/new",
        UploadJobCreateView.as_view(),
        name="upload_job_create",
    ),
    path("data-upload/", UploadAPIView.as_view(), name="data_upload"),
]
