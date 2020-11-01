from django.urls import path

from .views import (
    SelectiveTransferJobFormView,
    SelectiveTransferJobDetailView,
)

urlpatterns = [
    path(
        "selective-transfer/new/",
        SelectiveTransferJobFormView.as_view(),
        name="selective_transfer_job_form",
    ),
    path(
        "selective-transfers/<int:pk>/",
        SelectiveTransferJobDetailView.as_view(),
        name="selective_transfer_job_detail",
    ),
]
