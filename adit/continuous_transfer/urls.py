from django.urls import path

from .views import ContinuousTransferJobCreateView

urlpatterns = [
    path(
        "continuous-transfer/",
        ContinuousTransferJobCreateView.as_view(),
        name="continuous_transfer_job_create",
    ),
]
