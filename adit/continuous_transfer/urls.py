from django.urls import path
from .views import (
    ContinuousTransferJobListView,
    ContinuousTransferJobCreateView,
    ContinuousTransferJobDetailView,
    ContinuousTransferJobDeleteView,
    ContinuousTransferJobCancelView,
    ContinuousTransferJobVerifyView,
)

urlpatterns = [
    path(
        "",
        ContinuousTransferJobListView.as_view(),
        name="continuous_transfer_job_list",
    ),
    path(
        "new/",
        ContinuousTransferJobCreateView.as_view(),
        name="continuous_transfer_job_create",
    ),
    path(
        "<int:pk>/",
        ContinuousTransferJobDetailView.as_view(),
        name="continuous_transfer_job_detail",
    ),
    path(
        "<int:pk>/delete/",
        ContinuousTransferJobDeleteView.as_view(),
        name="continuous_transfer_job_delete",
    ),
    path(
        "<int:pk>/cancel/",
        ContinuousTransferJobCancelView.as_view(),
        name="continuous_transfer_job_cancel",
    ),
    path(
        "<int:pk>/verify/",
        ContinuousTransferJobVerifyView.as_view(),
        name="continuous_transfer_job_verify",
    ),
]
