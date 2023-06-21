from django.urls import path

from .views import (
    ContinuousTransferJobCancelView,
    ContinuousTransferJobCreateView,
    ContinuousTransferJobDeleteView,
    ContinuousTransferJobDetailView,
    ContinuousTransferJobListView,
    ContinuousTransferJobRestartView,
    ContinuousTransferJobResumeView,
    ContinuousTransferJobRetryView,
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
        "jobs/<int:pk>/verify/",
        ContinuousTransferJobVerifyView.as_view(),
        name="continuous_transfer_job_verify",
    ),
    path(
        "jobs/<int:pk>/cancel/",
        ContinuousTransferJobCancelView.as_view(),
        name="continuous_transfer_job_cancel",
    ),
    path(
        "jobs/<int:pk>/resume/",
        ContinuousTransferJobResumeView.as_view(),
        name="continuous_transfer_job_resume",
    ),
    path(
        "jobs/<int:pk>/retry/",
        ContinuousTransferJobRetryView.as_view(),
        name="continuous_transfer_job_retry",
    ),
    path(
        "jobs/<int:pk>/restart/",
        ContinuousTransferJobRestartView.as_view(),
        name="continuous_transfer_job_restart",
    ),
    path(
        "jobs/<int:pk>/verify/",
        ContinuousTransferJobVerifyView.as_view(),
        name="continuous_transfer_job_verify",
    ),
    path(
        "jobs/<int:job_id>/tasks/<int:task_id>/",
        ContinuousTransferTaskDetailView.as_view(),
        name="continuous_transfer_task_detail",
    ),
]
