from django.urls import path

from .views import SelectiveTransferJobCreate

urlpatterns = [
    path(
        "selective-transfer/",
        SelectiveTransferJobCreate.as_view(),
        name="query_studies",
    )
]
