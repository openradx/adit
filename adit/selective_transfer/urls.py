from django.urls import path

from .views import SelectiveTransferJobFormView, SelectiveTransferJobCreateAPIView

urlpatterns = [
    path(
        "selective-transfer/",
        SelectiveTransferJobFormView.as_view(),
        name="selective_transfer_job_form",
    ),
    path("selective-transfer/create/", SelectiveTransferJobCreateAPIView.as_view()),
]
