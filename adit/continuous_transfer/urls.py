from django.urls import path
from .views import (
    ContinuousTransferJobListView,
    ContinuousTransferJobCreateView,
    ContinuousTransferJobDetailView,
    ContinuousTransferJobDeleteView,
    ContinuousTransferJobCancelView,
    ContinuousTransferJobVerifyView,
    ContinuousTransferTaskDetailView,
)

urlpatterns = [
    path(
        "jobs/",
        ContinuousTransferJobListView.as_view(),
        name="continuous_transfer_job_list",
    ),
    path(
        "jobs/new/",
        ContinuousTransferJobCreateView.as_view(),
        name="continuous_transfer_job_create",
    ),
    path(
        "jobs/<int:pk>/",
        ContinuousTransferJobDetailView.as_view(),
        name="continuous_transfer_job_detail",
    ),
    path(
        "jobs/<int:pk>/delete/",
        ContinuousTransferJobDeleteView.as_view(),
        name="continuous_transfer_job_delete",
    ),
    path(
        "jobs/<int:pk>/cancel/",
        ContinuousTransferJobCancelView.as_view(),
        name="continuous_transfer_job_cancel",
    ),
    path(
        "jobs/<int:pk>/verify/",
        ContinuousTransferJobVerifyView.as_view(),
        name="continuous_transfer_job_verify",
    ),
    path(
        "tasks/<int:pk>/",
        ContinuousTransferTaskDetailView.as_view(),
        name="continuous_transfer_task_detail",
    ),
]
