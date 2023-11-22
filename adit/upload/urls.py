from django.urls import path

from .views import UploadDataView, UploadJobCreateView

urlpatterns = [
    path(
        "jobs/new",
        UploadJobCreateView.as_view(),
        name="upload_job_create",
    ),
    path("upload", UploadDataView.as_view(), name="upload_data"),
]
