from django.urls import path
from django.views.generic import TemplateView
from .views import (
    TransferJobListView,
    render_job_detail,
    TransferJobDelete,
    TransferJobCancel,
    FlowerProxyView,
)

urlpatterns = [
    path("", TemplateView.as_view(template_name="main/home.html"), name="home"),
    path("jobs/", TransferJobListView.as_view(), name="transfer_job_list"),
    path("jobs/<int:pk>/", render_job_detail, name="transfer_job_detail"),
    path(
        "jobs/<int:pk>/delete", TransferJobDelete.as_view(), name="transfer_job_delete"
    ),
    path(
        "jobs/<int:pk>/cancel", TransferJobCancel.as_view(), name="transfer_job_cancel"
    ),
    FlowerProxyView.as_url(),
]
