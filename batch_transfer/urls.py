from django.urls import path

from .views import BatchTransferJobCreateView

urlpatterns = [
    path(
        "batch-transfer/",
        BatchTransferJobCreateView.as_view(),
        name="batch_transfer_job_create",
    )
]
