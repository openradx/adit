from django.urls import path

from .views import (
    SelectiveTransferJobCreateView,
    SelectiveTransferJobDetailView,
)

urlpatterns = [
    path(
        "selective-transfer/new/",
        SelectiveTransferJobCreateView.as_view(),
        name="selective_transfer_job_form",
    ),
    path(
        "selective-transfers/<int:pk>/",
        SelectiveTransferJobDetailView.as_view(),
        name="selective_transfer_job_detail",
    ),
]
