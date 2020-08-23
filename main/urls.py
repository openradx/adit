from django.urls import path
from django.views.generic import TemplateView
from .views import (
    TransferJobListView,
    render_job_detail,
    TransferJobDelete,
    TransferJobCancel,
    FlowerProxyView,
    TransferJobListCreateAPIView,
)

urlpatterns = [
    path("", TemplateView.as_view(template_name="main/home.html"), name="home"),
    path("transfer-jobs/", TransferJobListView.as_view(), name="transfer_job_list"),
    path("transfer-jobs/<int:pk>/", render_job_detail, name="transfer_job_detail"),
    path(
        "transfer-jobs/<int:pk>/delete",
        TransferJobDelete.as_view(),
        name="transfer_job_delete",
    ),
    path(
        "transfer-jobs/<int:pk>/cancel",
        TransferJobCancel.as_view(),
        name="transfer_job_cancel",
    ),
    path(
        "api/transfer-jobs/",
        TransferJobListCreateAPIView.as_view(),
        name="transfer_job_list_create_api",
    ),
    FlowerProxyView.as_url(),
]
