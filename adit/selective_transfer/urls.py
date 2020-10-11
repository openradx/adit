from django.urls import path

from .views import (
    SelectiveTransferJobFormView,
    SelectiveTransferJobCreateAPIView,
    SelectiveTransferJobDetailView,
)

urlpatterns = [
    path(
        "selective-transfer/new/",
        SelectiveTransferJobFormView.as_view(),
        name="selective_transfer_job_form",
    ),
    path("selective-transfer/create/", SelectiveTransferJobCreateAPIView.as_view()),
    path(
        "selective-transfers/<int:pk>/",
        SelectiveTransferJobDetailView.as_view(),
        name="selective_transfer_job_detail",
    ),
]
