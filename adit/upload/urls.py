from django.urls import path
from .views import (
    UploadJobCreateView,
)

urlpatterns = [
    path(
        "jobs/new/",
        UploadJobCreateView.as_view(),
        name="upload_job_create"
    )
]