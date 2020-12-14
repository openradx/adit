from django.urls import path
from .views import (
    BatchTransferJobListView,
    BatchTransferJobCreateView,
    BatchTransferJobDetailView,
    BatchTransferJobDeleteView,
    BatchTransferJobCancelView,
    BatchTransferJobVerifyView,
    BatchTransferTaskDetailView,
)

urlpatterns = [
    path(
        "",
        BatchTransferJobListView.as_view(),
        name="batch_transfer_job_list",
    ),
    path(
        "new/",
        BatchTransferJobCreateView.as_view(),
        name="batch_transfer_job_create",
    ),
    path(
        "<int:pk>/",
        BatchTransferJobDetailView.as_view(),
        name="batch_transfer_job_detail",
    ),
    path(
        "<int:pk>/delete/",
        BatchTransferJobDeleteView.as_view(),
        name="batch_transfer_job_delete",
    ),
    path(
        "<int:pk>/cancel/",
        BatchTransferJobCancelView.as_view(),
        name="batch_transfer_job_cancel",
    ),
    path(
        "<int:pk>/verify/",
        BatchTransferJobVerifyView.as_view(),
        name="batch_transfer_job_verify",
    ),
    path(
        "tasks/<int:pk>/",
        BatchTransferTaskDetailView.as_view(),
        name="batch_transfer_task_detail",
    ),
]
