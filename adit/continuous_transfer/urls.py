from django.urls import path

from .views import ContinuousTransferJobCreateView, ContinuousTransferJobDetailView

urlpatterns = [
    path(
        "continuous-transfer/",
        ContinuousTransferJobCreateView.as_view(),
        name="continuous_transfer_job_create",
    ),
    path(
        "continuous-transfers/<int:pk>/",
        ContinuousTransferJobDetailView.as_view(),
        name="continuous_transfer_job_detail",
    ),
]
