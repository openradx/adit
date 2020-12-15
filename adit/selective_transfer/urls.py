from django.urls import path
from .views import (
    SelectiveTransferJobListView,
    SelectiveTransferJobCreateView,
    SelectiveTransferJobDetailView,
    SelectiveTransferJobDeleteView,
    SelectiveTransferJobCancelView,
    SelectiveTransferJobVerifyView,
)

urlpatterns = [
    path(
        "",
        SelectiveTransferJobListView.as_view(),
        name="selective_transfer_job_list",
    ),
    path(
        "new/",
        SelectiveTransferJobCreateView.as_view(),
        name="selective_transfer_job_form",
    ),
    path(
        "<int:pk>/",
        SelectiveTransferJobDetailView.as_view(),
        name="selective_transfer_job_detail",
    ),
    path(
        "<int:pk>/delete/",
        SelectiveTransferJobDeleteView.as_view(),
        name="selective_transfer_job_delete",
    ),
    path(
        "<int:pk>/cancel/",
        SelectiveTransferJobCancelView.as_view(),
        name="selective_transfer_job_cancel",
    ),
    path(
        "<int:pk>/verify/",
        SelectiveTransferJobVerifyView.as_view(),
        name="selective_transfer_job_verify",
    ),
]
