from django.urls import path

from .views import TransferJobListCreateAPIView

urlpatterns = [
    path(
        "transfer-jobs/",
        TransferJobListCreateAPIView.as_view(),
        name="transfer_job_list_create_api",
    ),
]
