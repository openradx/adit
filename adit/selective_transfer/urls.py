from django.urls import path

from .views import (
    SelectiveTransferJobCreateView,
    SelectiveTransferJobDetailView,
    SelectiveTransferJobTaskView,
)

urlpatterns = [
    path(
        "selective-transfers/new/",
        SelectiveTransferJobCreateView.as_view(),
        name="selective_transfer_job_form",
    ),
    path(
        "selective-transfers/<int:pk>/",
        SelectiveTransferJobDetailView.as_view(),
        name="selective_transfer_job_detail",
    ),
    path(
        "selective-transfers/<int:pk>/tasks/<int:task_id>/",
        SelectiveTransferJobTaskView.as_view(),
        name="selective_transfer_job_task",
    ),
]
