from django.urls import path
from .views import (
    SelectiveTransferJobListView,
    SelectiveTransferJobCreateView,
    SelectiveTransferJobDetailView,
    SelectiveTransferJobDeleteView,
    SelectiveTransferJobCancelView,
    SelectiveTransferJobVerifyView,
    SelectiveTransferTaskDetailView,
)

urlpatterns = [
    path(
        "jobs/",
        SelectiveTransferJobListView.as_view(),
        name="selective_transfer_job_list",
    ),
    path(
        "jobs/new/",
        SelectiveTransferJobCreateView.as_view(),
        name="selective_transfer_job_form",
    ),
    path(
        "jobs/<int:pk>/",
        SelectiveTransferJobDetailView.as_view(),
        name="selective_transfer_job_detail",
    ),
    path(
        "jobs/<int:pk>/delete/",
        SelectiveTransferJobDeleteView.as_view(),
        name="selective_transfer_job_delete",
    ),
    path(
        "jobs/<int:pk>/cancel/",
        SelectiveTransferJobCancelView.as_view(),
        name="selective_transfer_job_cancel",
    ),
    path(
        "jobs/<int:pk>/verify/",
        SelectiveTransferJobVerifyView.as_view(),
        name="selective_transfer_job_verify",
    ),
    path(
        "tasks/<int:pk>/",
        SelectiveTransferTaskDetailView.as_view(),
        name="selective_transfer_task_detail",
    ),
]
