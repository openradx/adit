from django.urls import path
from .views import TransferJobListAPIView

urlpatterns = [
    path(
        "transfer-jobs/",
        TransferJobListAPIView.as_view(),
    ),
]
