from django.urls import path

from .views import BatchTransferJobCreateView, BatchTransferJobDetailView

urlpatterns = [
    path(
        "batch-transfers/new",
        BatchTransferJobCreateView.as_view(),
        name="batch_transfer_job_create",
    ),
    path(
        "batch-transfers/<int:pk>/",
        BatchTransferJobDetailView.as_view(),
        name="batch_transfer_job_detail",
    ),
]
